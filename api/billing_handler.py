"""
Billing handler — Stripe Checkout and Customer Portal (Task 3.1).

POST /api/tenant/billing/checkout — create Checkout Session for subscription
POST /api/tenant/billing/portal — create Customer Portal session
"""

import json
import os
from datetime import datetime, timezone

import boto3

from auth_helpers import require_tenant_auth, require_tenant_admin_or_manager, role_is_admin_or_manager
from dynamodb_helpers import get_tenant_item
from middleware import with_tenant
from stripe_helpers import get_stripe_api_key, get_stripe_price_id, stripe_configured


def _json_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _get_tenant(table, tenant_slug: str) -> dict | None:
    resp = table.get_item(Key=get_tenant_item(tenant_slug))
    return resp.get("Item")


def _update_tenant_stripe_customer(table, tenant_slug: str, stripe_customer_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    table.update_item(
        Key=get_tenant_item(tenant_slug),
        UpdateExpression="SET stripe_customer_id = :cid, updated_at = :u",
        ExpressionAttributeValues={":cid": stripe_customer_id, ":u": now},
    )


@with_tenant
def billing_checkout_handler(event: dict, context: dict) -> dict:
    """
    POST /api/tenant/billing/checkout — create Stripe Checkout Session for subscription.

    Body: { "tier": "pro"|"business", "success_url": "...", "cancel_url": "..." }
    Requires: tenant_slug, Cognito auth, admin/manager role.
    """
    if not stripe_configured():
        return _json_response(503, {"error": "Billing is not configured."})

    tenant_slug = event.get("tenant_slug")
    if not tenant_slug:
        return _json_response(
            400,
            {"error": "Missing tenant. Use subdomain or X-Tenant-Slug header."},
        )

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    region = os.environ.get("AWS_REGION", "us-east-1")
    auth_result = require_tenant_auth(event, table, tenant_slug, region)
    if auth_result[0] is not True:
        _, err_resp = auth_result
        return _json_response(err_resp.get("statusCode", 401), json.loads(err_resp.get("body", "{}")))
    _, sub_or_username, role, is_cognito = auth_result
    sub = sub_or_username if is_cognito else None

    if is_cognito:
        ok, err = require_tenant_admin_or_manager(table, sub, tenant_slug)
        if not ok:
            return _json_response(403, {"error": err or "Forbidden."})
    elif not role_is_admin_or_manager(role):
        return _json_response(403, {"error": "Admin or manager role required."})

    body = event.get("body") or "{}"
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            return _json_response(400, {"error": "Invalid JSON body."})

    tier = (body.get("tier") or "").lower()
    if tier not in ("pro", "business"):
        return _json_response(400, {"error": "tier must be pro or business."})

    price_id = get_stripe_price_id(tier)
    if not price_id:
        return _json_response(503, {"error": f"Price for tier {tier} is not configured."})

    success_url = (body.get("success_url") or "").strip()
    cancel_url = (body.get("cancel_url") or "").strip()
    if not success_url or not cancel_url:
        return _json_response(400, {"error": "success_url and cancel_url are required."})

    import stripe

    stripe.api_key = get_stripe_api_key()
    tenant = _get_tenant(table, tenant_slug)
    stripe_customer_id = (tenant or {}).get("stripe_customer_id")

    session_params = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": tenant_slug,
        "metadata": {"tenant_slug": tenant_slug},
        "subscription_data": {"metadata": {"tenant_slug": tenant_slug}},
    }

    if stripe_customer_id:
        session_params["customer"] = stripe_customer_id
    else:
        session_params["customer_creation"] = "always"

    try:
        session = stripe.checkout.Session.create(**session_params)
        return _json_response(200, {"url": session.url, "session_id": session.id})
    except stripe.StripeError as e:
        return _json_response(502, {"error": str(e) or "Stripe error."})


@with_tenant
def billing_portal_handler(event: dict, context: dict) -> dict:
    """
    POST /api/tenant/billing/portal — create Stripe Customer Portal session.

    Body: { "return_url": "..." }
    Requires: tenant_slug, Cognito auth, admin/manager role.
    """
    if not stripe_configured():
        return _json_response(503, {"error": "Billing is not configured."})

    tenant_slug = event.get("tenant_slug")
    if not tenant_slug:
        return _json_response(
            400,
            {"error": "Missing tenant. Use subdomain or X-Tenant-Slug header."},
        )

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    region = os.environ.get("AWS_REGION", "us-east-1")
    auth_result = require_tenant_auth(event, table, tenant_slug, region)
    if auth_result[0] is not True:
        _, err_resp = auth_result
        return _json_response(err_resp.get("statusCode", 401), json.loads(err_resp.get("body", "{}")))
    _, sub_or_username, role, is_cognito = auth_result
    sub = sub_or_username if is_cognito else None

    if is_cognito:
        ok, err = require_tenant_admin_or_manager(table, sub, tenant_slug)
        if not ok:
            return _json_response(403, {"error": err or "Forbidden."})
    elif not role_is_admin_or_manager(role):
        return _json_response(403, {"error": "Admin or manager role required."})

    tenant = _get_tenant(table, tenant_slug)
    stripe_customer_id = (tenant or {}).get("stripe_customer_id")
    if not stripe_customer_id:
        return _json_response(
            400,
            {"error": "No billing account. Subscribe first via checkout."},
        )

    body = event.get("body") or "{}"
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            return _json_response(400, {"error": "Invalid JSON body."})

    return_url = (body.get("return_url") or "").strip()
    if not return_url:
        return _json_response(400, {"error": "return_url is required."})

    import stripe

    stripe.api_key = get_stripe_api_key()
    try:
        session = stripe.billing_portal.Session.create(
            customer=stripe_customer_id,
            return_url=return_url,
        )
        return _json_response(200, {"url": session.url})
    except stripe.StripeError as e:
        return _json_response(502, {"error": str(e) or "Stripe error."})
