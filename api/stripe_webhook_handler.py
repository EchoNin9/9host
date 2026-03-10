"""
Stripe webhook route — POST /api/webhooks/stripe (Task 1.19).

Handler stub for agent3. Stripe sends events here; agent3 will verify
Stripe-Signature and process subscription events (3.3).
No Cognito auth — Stripe authenticates via webhook signing secret.
"""

import json


def _json_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def stripe_webhook_handler(event: dict, context: dict) -> dict:
    """
    POST /api/webhooks/stripe — Stripe webhook endpoint.

    Stub: returns 200 with received=true. Agent3 will:
    - Verify Stripe-Signature using STRIPE_WEBHOOK_SECRET
    - Parse event type and process (customer.subscription.updated, etc.)
    - Map subscription status to tier for FeatureFlag
    """
    if event.get("requestContext", {}).get("http", {}).get("method") != "POST":
        return _json_response(405, {"error": "Method not allowed."})

    body = event.get("body") or ""
    return _json_response(200, {"received": True, "stub": True})
