# Stripe Integration (Task 3.1)

9host uses Stripe for tier subscriptions (Free, Pro, Business). Pro and Business tiers are paid via Stripe Checkout; webhooks sync subscription status to tenant tier.

## Setup

### 1. Create Stripe products and prices

In [Stripe Dashboard](https://dashboard.stripe.com/products):

1. Create product **Pro** with a recurring price (e.g. monthly or yearly).
2. Create product **Business** with a recurring price.
3. Copy each Price ID (e.g. `price_1ABC...`).

### 2. Configure webhook

1. In Stripe Dashboard → Developers → Webhooks, add endpoint:
   - URL: `https://<api-gateway-url>/api/webhooks/stripe`
   - Events: `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`
2. Copy the webhook signing secret (`whsec_...`).

### 3. Store credentials in Secrets Manager

```bash
aws secretsmanager put-secret-value --secret-id 9host-stripe \
  --secret-string '{
    "secret_key": "sk_live_...",
    "webhook_secret": "whsec_...",
    "price_pro": "price_...",
    "price_business": "price_..."
  }'
```

Use `sk_test_...` and test-mode webhook secret for staging.

## API

### POST /api/tenant/billing/checkout

Creates a Stripe Checkout Session for subscription. Redirect user to `url` to complete payment.

**Body:**
```json
{
  "tier": "pro",
  "success_url": "https://acme.echo9.net/settings?checkout=success",
  "cancel_url": "https://acme.echo9.net/settings?checkout=cancel"
}
```

**Response (200):**
```json
{
  "url": "https://checkout.stripe.com/...",
  "session_id": "cs_..."
}
```

### POST /api/tenant/billing/portal

Creates a Stripe Customer Portal session. Use when tenant already has a subscription (from checkout).

**Body:**
```json
{
  "return_url": "https://acme.echo9.net/settings"
}
```

**Response (200):**
```json
{
  "url": "https://billing.stripe.com/..."
}
```

## Webhook events

| Event | Action |
|-------|--------|
| `checkout.session.completed` | Set `stripe_customer_id` on tenant |
| `customer.subscription.created` | Set tenant tier from price |
| `customer.subscription.updated` | Update tenant tier |
| `customer.subscription.deleted` | Set tier to FREE |

Subscription metadata must include `tenant_slug` (set automatically by checkout).
