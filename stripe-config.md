# Stripe Integration (Task 3.1) — Config & Setup

## Summary of Changes

### Backend (API)

1. **`api/requirements.txt`** — Added Stripe SDK dependency.
2. **`api/stripe_helpers.py`** — Helper to load Stripe config from Secrets Manager.
3. **`api/billing_handler.py`** — Billing endpoints:
   - **POST /api/tenant/billing/checkout** — Creates Stripe Checkout Session for Pro/Business subscriptions.
   - **POST /api/tenant/billing/portal** — Creates Stripe Customer Portal session for managing subscriptions.
4. **`api/stripe_webhook_handler.py`** — Webhook handler that:
   - Verifies `Stripe-Signature`
   - Handles `checkout.session.completed`, `customer.subscription.created/updated/deleted`
   - Updates tenant `tier`, `stripe_customer_id`, `stripe_subscription_id` in DynamoDB.

### Infrastructure

5. **`infra/secrets.tf`** — Added `9host-stripe` secret for `secret_key`, `webhook_secret`, `price_pro`, `price_business`.
6. **`infra/lambda.tf`** — Added `STRIPE_SECRET_ARN` env var and Secrets Manager read permission for the Lambda.
7. **`.github/workflows/dev.yml`** and **`main.yml`** — Added `pip install -r api/requirements.txt -t api/` before tofu apply.

### Frontend

8. **`frontend/src/lib/api.ts`** — Added `createBillingCheckout` and `createBillingPortal` API helpers.

### Documentation

9. **`docs/STRIPE.md`** — Stripe setup and usage.
10. **`docs/API.md`** — Documented billing endpoints.
11. **`docs/SCHEMA.md`** — Documented `stripe_subscription_id` on Tenant.
12. **`TASKS.md`** — Marked task 3.1 as DONE.

---

## Next Steps

1. **Create Stripe products** — In Stripe Dashboard, create Pro and Business products and copy their Price IDs.
2. **Configure webhook** — Add `https://<api-url>/api/webhooks/stripe` and subscribe to the listed events.
3. **Set secret** — Store Stripe credentials in Secrets Manager:
   ```bash
   aws secretsmanager put-secret-value --secret-id 9host-stripe \
     --secret-string '{"secret_key":"sk_...","webhook_secret":"whsec_...","price_pro":"price_...","price_business":"price_..."}'
   ```
4. **Commit and deploy** — Commit the changes and push to trigger CI.

To run roborev after committing:

```bash
git add -A && git commit -m "agent3 task 3.1: Integrate Stripe for tier subscriptions"
roborev refine
```
