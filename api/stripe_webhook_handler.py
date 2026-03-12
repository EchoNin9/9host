"""
Stripe webhook route — POST /api/webhooks/stripe (Task 1.19, 3.1).

Verifies Stripe-Signature and processes subscription events.
No Cognito auth — Stripe authenticates via webhook signing secret.
"""

import json
import os
from datetime import datetime, timezone

import boto3

from dynamodb_helpers import get_tenant_item
from stripe_helpers import get_stripe_api_key, get_stripe_webhook_secret


def _json_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _get_header(event: dict, name: str) -> str:
    headers = event.get("headers") or {}
    key_lower = name.lower()
    if isinstance(headers, dict):
        for k, v in headers.items():
            if (k or "").lower() == key_lower:
                return (v or "").strip()
        return ""
    for h in headers:
        k = (h.get("key") or h.get("Key") or "").lower()
        if k == key_lower:
            return (h.get("value") or h.get("Value") or "").strip()
    return ""


def _tier_from_price_id(price_id: str) -> str:
    """Map Stripe Price ID to tier (PRO, BUSINESS)."""
    cfg = _get_stripe_config()
    if not cfg:
        return "FREE"
    if price_id == cfg.get("price_pro"):
        return "PRO"
    if price_id == cfg.get("price_business"):
        return "BUSINESS"
    return "FREE"


def _get_stripe_config() -> dict | None:
    arn = os.environ.get("STRIPE_SECRET_ARN")
    if not arn:
        return None
    try:
        client = boto3.client("secretsmanager")
        resp = client.get_secret_value(SecretId=arn)
        raw = resp.get("SecretString", "{}")
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _handle_subscription_event(subscription: dict, table) -> None:
    """
    Update tenant from subscription. metadata.tenant_slug required.
    """
    metadata = subscription.get("metadata") or {}
    tenant_slug = metadata.get("tenant_slug")
    if not tenant_slug:
        return

    customer_id = subscription.get("customer")
    if isinstance(customer_id, dict):
        customer_id = customer_id.get("id")
    status = (subscription.get("status") or "").lower()

    now = datetime.now(timezone.utc).isoformat()

    if status == "active":
        price_id = None
        items = subscription.get("items") or {}
        data = items.get("data") or []
        if data:
            price = (data[0] or {}).get("price") or {}
            price_id = price.get("id") if isinstance(price, dict) else None
        tier = _tier_from_price_id(price_id) if price_id else "PRO"

        updates = ["tier = :tier", "updated_at = :u"]
        values = {":tier": tier, ":u": now}
        if customer_id:
            updates.append("stripe_customer_id = :cid")
            values[":cid"] = customer_id
        sub_id = subscription.get("id")
        if sub_id:
            updates.append("stripe_subscription_id = :subid")
            values[":subid"] = sub_id

        table.update_item(
            Key=get_tenant_item(tenant_slug),
            UpdateExpression="SET " + ", ".join(updates),
            ExpressionAttributeValues=values,
        )
    else:
        table.update_item(
            Key=get_tenant_item(tenant_slug),
            UpdateExpression="SET tier = :tier, updated_at = :u REMOVE stripe_subscription_id",
            ExpressionAttributeValues={":tier": "FREE", ":u": now},
        )


def _handle_checkout_completed(session: dict, table) -> None:
    """Set stripe_customer_id and tier from completed checkout."""
    tenant_slug = (
        (session.get("metadata") or {}).get("tenant_slug")
        or session.get("client_reference_id")
    )
    if not tenant_slug:
        return

    customer_id = session.get("customer")
    if isinstance(customer_id, dict):
        customer_id = customer_id.get("id")
    subscription_id = session.get("subscription")

    if not customer_id:
        return

    now = datetime.now(timezone.utc).isoformat()
    table.update_item(
        Key=get_tenant_item(tenant_slug),
        UpdateExpression="SET stripe_customer_id = :cid, updated_at = :u",
        ExpressionAttributeValues={":cid": customer_id, ":u": now},
    )
    if subscription_id:
        table.update_item(
            Key=get_tenant_item(tenant_slug),
            UpdateExpression="SET stripe_subscription_id = :subid, updated_at = :u",
            ExpressionAttributeValues={":subid": subscription_id, ":u": now},
        )


def stripe_webhook_handler(event: dict, context: dict) -> dict:
    """
    POST /api/webhooks/stripe — Stripe webhook endpoint.

    Verifies Stripe-Signature, processes subscription events, updates tenant tier.
    """
    if event.get("requestContext", {}).get("http", {}).get("method") != "POST":
        return _json_response(405, {"error": "Method not allowed."})

    body = event.get("body") or ""
    sig_header = _get_header(event, "Stripe-Signature")
    secret = get_stripe_webhook_secret()

    if not secret or secret == "REPLACE_ME":
        return _json_response(200, {"received": True, "skipped": "webhook not configured"})

    try:
        import stripe

        stripe.api_key = get_stripe_api_key()
        evt = stripe.Webhook.construct_event(body, sig_header, secret)
    except ValueError as e:
        return _json_response(400, {"error": f"Invalid payload: {e}"})
    except Exception as e:
        return _json_response(400, {"error": f"Invalid signature: {e}"})

    event_type = evt.get("type", "")
    data = evt.get("data") or {}
    obj = data.get("object") or {}

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    if event_type == "checkout.session.completed":
        mode = (obj.get("mode") or "").lower()
        if mode == "subscription":
            _handle_checkout_completed(obj, table)
    elif event_type in (
        "customer.subscription.created",
        "customer.subscription.updated",
    ):
        _handle_subscription_event(obj, table)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_event(obj, table)

    return _json_response(200, {"received": True})
