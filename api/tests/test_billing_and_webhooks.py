"""
Tests for billing handler and stripe webhook handler (Ticket T-05 / Bug #6).

Verifies:
- BILLING_ENABLED feature flag on backend (default disabled -> 403)
- Bug #6a: FREE tenant allowed to start checkout; VIP tenant blocked from checkout and portal
- Bug #6b: isBase64Encoded payloads decoded before webhook signature verification
- Bug #6b: trialing subscription status treated as active
- Bug #6b: VIP tenant tier never overwritten/downgraded on cancellation/unpaid/deleted
- Non-VIP tenant downgraded to FREE on subscription deleted
- Webhooks keep processing even if BILLING_ENABLED is false
"""

import base64
import json
from unittest.mock import MagicMock, patch

import pytest
import billing_handler
import stripe_webhook_handler
from dynamodb_helpers import get_tenant_item


@pytest.fixture
def mock_stripe_config():
    """Mock config returned by Secrets Manager."""
    return {
        "secret_key": "sk_test_mock_key_123",
        "webhook_secret": "whsec_mock_webhook_secret_456",
        "price_pro": "price_pro_test_123",
        "price_business": "price_biz_test_456",
    }


@pytest.fixture
def auth_mock(monkeypatch):
    """Bypass auth helpers for billing tests."""
    monkeypatch.setattr(
        "billing_handler.require_tenant_auth",
        lambda event, table, tenant_slug, region: (True, "sub_admin_123", "admin", True),
    )
    monkeypatch.setattr(
        "billing_handler.require_tenant_admin_or_manager",
        lambda table, sub, tenant_slug, event: (True, None),
    )


class TestBillingFeatureFlag:
    def test_checkout_rejected_when_billing_disabled(self, dynamodb_table, auth_mock, monkeypatch):
        """When BILLING_ENABLED is false or unset, checkout returns 403."""
        monkeypatch.delenv("BILLING_ENABLED", raising=False)
        event = {
            "tenant_slug": "tenant-free",
            "headers": {"x-tenant-slug": "tenant-free"},
            "body": json.dumps({
                "tier": "pro",
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            }),
        }
        resp = billing_handler.billing_checkout_handler(event, {})
        assert resp["statusCode"] == 403
        data = json.loads(resp["body"])
        assert data.get("error") == "Billing is disabled"

    def test_portal_rejected_when_billing_disabled(self, dynamodb_table, auth_mock, monkeypatch):
        """When BILLING_ENABLED is false or unset, portal returns 403."""
        monkeypatch.setenv("BILLING_ENABLED", "false")
        event = {
            "tenant_slug": "tenant-free",
            "headers": {"x-tenant-slug": "tenant-free"},
            "body": json.dumps({"return_url": "https://example.com/settings"}),
        }
        resp = billing_handler.billing_portal_handler(event, {})
        assert resp["statusCode"] == 403
        data = json.loads(resp["body"])
        assert data.get("error") == "Billing is disabled"


class TestBillingCheckoutAndPortal:
    def test_free_tenant_checkout_allowed(
        self, dynamodb_table, auth_mock, mock_stripe_config, monkeypatch
    ):
        """Bug #6a: FREE tenant must be able to initiate checkout to upgrade."""
        monkeypatch.setenv("BILLING_ENABLED", "true")
        monkeypatch.setattr("stripe_helpers._get_stripe_config", lambda: mock_stripe_config)

        tenant_slug = "tenant-free"
        dynamodb_table.put_item(
            Item={
                **get_tenant_item(tenant_slug),
                "tenant_slug": tenant_slug,
                "name": "Free Tenant",
                "tier": "FREE",
            }
        )

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/pay/cs_test_123"
        mock_session.id = "cs_test_123"

        with patch("stripe.checkout.Session.create", return_value=mock_session) as mock_create:
            event = {
                "tenant_slug": tenant_slug,
                "headers": {"x-tenant-slug": tenant_slug},
                "body": json.dumps({
                    "tier": "pro",
                    "success_url": "https://echo9.net/success",
                    "cancel_url": "https://echo9.net/cancel",
                }),
            }
            resp = billing_handler.billing_checkout_handler(event, {})
            assert resp["statusCode"] == 200
            data = json.loads(resp["body"])
            assert data["url"] == "https://checkout.stripe.com/pay/cs_test_123"
            assert data["session_id"] == "cs_test_123"

            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["line_items"][0]["price"] == "price_pro_test_123"
            assert call_kwargs["client_reference_id"] == tenant_slug

    def test_vip_tenant_blocked_from_checkout(
        self, dynamodb_table, auth_mock, mock_stripe_config, monkeypatch
    ):
        """VIP tenant should be blocked from checkout with 400."""
        monkeypatch.setenv("BILLING_ENABLED", "true")
        monkeypatch.setattr("stripe_helpers._get_stripe_config", lambda: mock_stripe_config)

        tenant_slug = "tenant-vip"
        dynamodb_table.put_item(
            Item={
                **get_tenant_item(tenant_slug),
                "tenant_slug": tenant_slug,
                "name": "VIP Tenant",
                "tier": "VIP",
            }
        )

        event = {
            "tenant_slug": tenant_slug,
            "headers": {"x-tenant-slug": tenant_slug},
            "body": json.dumps({
                "tier": "pro",
                "success_url": "https://echo9.net/success",
                "cancel_url": "https://echo9.net/cancel",
            }),
        }
        resp = billing_handler.billing_checkout_handler(event, {})
        assert resp["statusCode"] == 400
        data = json.loads(resp["body"])
        assert "VIP tier does not require billing" in data.get("error", "")

    def test_vip_tenant_blocked_from_portal(
        self, dynamodb_table, auth_mock, mock_stripe_config, monkeypatch
    ):
        """VIP tenant should be blocked from portal with 400."""
        monkeypatch.setenv("BILLING_ENABLED", "true")
        monkeypatch.setattr("stripe_helpers._get_stripe_config", lambda: mock_stripe_config)

        tenant_slug = "tenant-vip-portal"
        dynamodb_table.put_item(
            Item={
                **get_tenant_item(tenant_slug),
                "tenant_slug": tenant_slug,
                "name": "VIP Portal Tenant",
                "tier": "VIP",
                "stripe_customer_id": "cus_vip123",
            }
        )

        event = {
            "tenant_slug": tenant_slug,
            "headers": {"x-tenant-slug": tenant_slug},
            "body": json.dumps({"return_url": "https://echo9.net/settings"}),
        }
        resp = billing_handler.billing_portal_handler(event, {})
        assert resp["statusCode"] == 400
        data = json.loads(resp["body"])
        assert "VIP tier does not require billing" in data.get("error", "")


class TestStripeWebhookHandler:
    def test_webhook_decodes_base64_payload(
        self, dynamodb_table, mock_stripe_config, monkeypatch
    ):
        """Bug #6b: API Gateway isBase64Encoded payload is decoded before signature verification."""
        monkeypatch.setattr(
            "stripe_webhook_handler._get_stripe_config", lambda: mock_stripe_config
        )
        monkeypatch.setattr(
            "stripe_helpers._get_stripe_config", lambda: mock_stripe_config
        )

        raw_payload = json.dumps({
            "id": "evt_test_123",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "mode": "subscription",
                    "client_reference_id": "tenant-sub",
                    "customer": "cus_test_123",
                    "subscription": "sub_test_456",
                }
            },
        })
        b64_payload = base64.b64encode(raw_payload.encode("utf-8")).decode("utf-8")

        mock_event_obj = json.loads(raw_payload)

        with patch("stripe.Webhook.construct_event", return_value=mock_event_obj) as mock_construct:
            event = {
                "requestContext": {"http": {"method": "POST"}},
                "headers": {"Stripe-Signature": "t=123,v1=signature"},
                "body": b64_payload,
                "isBase64Encoded": True,
            }
            resp = stripe_webhook_handler.stripe_webhook_handler(event, {})
            assert resp["statusCode"] == 200

            # Verify that construct_event was called with the decoded string/bytes, not base64
            mock_construct.assert_called_once()
            called_payload = mock_construct.call_args[0][0]
            if isinstance(called_payload, bytes):
                called_payload = called_payload.decode("utf-8")
            assert json.loads(called_payload)["id"] == "evt_test_123"

    def test_webhook_trialing_treated_as_active(
        self, dynamodb_table, mock_stripe_config, monkeypatch
    ):
        """Bug #6b: Subscription status 'trialing' treated as active."""
        monkeypatch.setattr(
            "stripe_webhook_handler._get_stripe_config", lambda: mock_stripe_config
        )
        monkeypatch.setattr(
            "stripe_helpers._get_stripe_config", lambda: mock_stripe_config
        )

        tenant_slug = "tenant-trial"
        dynamodb_table.put_item(
            Item={
                **get_tenant_item(tenant_slug),
                "tenant_slug": tenant_slug,
                "tier": "FREE",
            }
        )

        evt_payload = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_trial_123",
                    "customer": "cus_trial_456",
                    "status": "trialing",
                    "metadata": {"tenant_slug": tenant_slug},
                    "items": {
                        "data": [
                            {"price": {"id": "price_pro_test_123"}}
                        ]
                    },
                }
            },
        }

        with patch("stripe.Webhook.construct_event", return_value=evt_payload):
            event = {
                "requestContext": {"http": {"method": "POST"}},
                "headers": {"Stripe-Signature": "sig"},
                "body": json.dumps(evt_payload),
                "isBase64Encoded": False,
            }
            resp = stripe_webhook_handler.stripe_webhook_handler(event, {})
            assert resp["statusCode"] == 200

        # Check tenant updated to PRO
        item = dynamodb_table.get_item(Key=get_tenant_item(tenant_slug)).get("Item")
        assert item["tier"] == "PRO"
        assert item["stripe_subscription_id"] == "sub_trial_123"
        assert item["stripe_customer_id"] == "cus_trial_456"

    def test_webhook_vip_never_downgraded_on_subscription_deleted(
        self, dynamodb_table, mock_stripe_config, monkeypatch
    ):
        """Bug #6b: VIP tenant tier is never downgraded to FREE on subscription deleted/unpaid."""
        monkeypatch.setattr(
            "stripe_webhook_handler._get_stripe_config", lambda: mock_stripe_config
        )
        monkeypatch.setattr(
            "stripe_helpers._get_stripe_config", lambda: mock_stripe_config
        )

        tenant_slug = "tenant-vip-preserve"
        dynamodb_table.put_item(
            Item={
                **get_tenant_item(tenant_slug),
                "tenant_slug": tenant_slug,
                "tier": "VIP",
                "stripe_customer_id": "cus_vip_999",
                "stripe_subscription_id": "sub_vip_old",
            }
        )

        evt_payload = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_vip_old",
                    "customer": "cus_vip_999",
                    "status": "canceled",
                    "metadata": {"tenant_slug": tenant_slug},
                }
            },
        }

        with patch("stripe.Webhook.construct_event", return_value=evt_payload):
            event = {
                "requestContext": {"http": {"method": "POST"}},
                "headers": {"Stripe-Signature": "sig"},
                "body": json.dumps(evt_payload),
            }
            resp = stripe_webhook_handler.stripe_webhook_handler(event, {})
            assert resp["statusCode"] == 200

        # Verify tenant is still VIP!
        item = dynamodb_table.get_item(Key=get_tenant_item(tenant_slug)).get("Item")
        assert item["tier"] == "VIP"

    def test_webhook_non_vip_downgraded_on_subscription_deleted(
        self, dynamodb_table, mock_stripe_config, monkeypatch
    ):
        """Non-VIP tenant (e.g. PRO) is downgraded to FREE on cancellation."""
        monkeypatch.setattr(
            "stripe_webhook_handler._get_stripe_config", lambda: mock_stripe_config
        )
        monkeypatch.setattr(
            "stripe_helpers._get_stripe_config", lambda: mock_stripe_config
        )

        tenant_slug = "tenant-pro-cancelling"
        dynamodb_table.put_item(
            Item={
                **get_tenant_item(tenant_slug),
                "tenant_slug": tenant_slug,
                "tier": "PRO",
                "stripe_customer_id": "cus_pro_999",
                "stripe_subscription_id": "sub_pro_123",
            }
        )

        evt_payload = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_pro_123",
                    "customer": "cus_pro_999",
                    "status": "canceled",
                    "metadata": {"tenant_slug": tenant_slug},
                }
            },
        }

        with patch("stripe.Webhook.construct_event", return_value=evt_payload):
            event = {
                "requestContext": {"http": {"method": "POST"}},
                "headers": {"Stripe-Signature": "sig"},
                "body": json.dumps(evt_payload),
            }
            resp = stripe_webhook_handler.stripe_webhook_handler(event, {})
            assert resp["statusCode"] == 200

        item = dynamodb_table.get_item(Key=get_tenant_item(tenant_slug)).get("Item")
        assert item["tier"] == "FREE"
        assert "stripe_subscription_id" not in item

    def test_webhook_runs_even_when_billing_disabled(
        self, dynamodb_table, mock_stripe_config, monkeypatch
    ):
        """Webhooks process incoming events even if BILLING_ENABLED is false."""
        monkeypatch.setenv("BILLING_ENABLED", "false")
        monkeypatch.setattr(
            "stripe_webhook_handler._get_stripe_config", lambda: mock_stripe_config
        )
        monkeypatch.setattr(
            "stripe_helpers._get_stripe_config", lambda: mock_stripe_config
        )

        tenant_slug = "tenant-webhook-disabled-flag"
        dynamodb_table.put_item(
            Item={
                **get_tenant_item(tenant_slug),
                "tenant_slug": tenant_slug,
                "tier": "FREE",
            }
        )

        evt_payload = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_active_123",
                    "customer": "cus_active_456",
                    "status": "active",
                    "metadata": {"tenant_slug": tenant_slug},
                    "items": {
                        "data": [
                            {"price": {"id": "price_pro_test_123"}}
                        ]
                    },
                }
            },
        }

        with patch("stripe.Webhook.construct_event", return_value=evt_payload):
            event = {
                "requestContext": {"http": {"method": "POST"}},
                "headers": {"Stripe-Signature": "sig"},
                "body": json.dumps(evt_payload),
            }
            resp = stripe_webhook_handler.stripe_webhook_handler(event, {})
            assert resp["statusCode"] == 200

        item = dynamodb_table.get_item(Key=get_tenant_item(tenant_slug)).get("Item")
        assert item["tier"] == "PRO"
