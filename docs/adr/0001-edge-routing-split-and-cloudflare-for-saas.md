# ADR-0001: Edge Routing Split, CloudFront KVS, and Cloudflare for SaaS Custom Domains

- **Status:** Accepted
- **Date:** 2026-11-10
- **Deciders:** Adam, Architecture Review Session

---

## Context

In the initial 9host architecture:
1. **Single-Distribution Routing Bottleneck:** `aws_cloudfront_distribution.sites` (`*.echo9.net`) routed its default behavior (`/*`) to the React Admin SPA S3 bucket (`9host-frontend-*`). When a visitor navigated to `https://<slug>.echo9.net/`, their browser downloaded the entire React Admin SPA, executed `RootRoute` (`frontend/src/App.tsx`), made a cold-start API Gateway + Lambda + DynamoDB call to `GET /api/tenant/default-site` (`api/default_site_handler.py`), and executed `window.location.replace("/site/{tenant}/{site_id}/")`. This added 3 network hops, broke SEO, exposed ugly `/site/{tenant}/{site_id}/` URLs, and incurred Lambda + DynamoDB costs on every visitor landing.
2. **Broken Per-Domain ACM Certificate Flow:** `api/custom_domain_handler.py` requested a standalone AWS ACM certificate per custom domain and attempted to append the custom domain to `aws_cloudfront_distribution.sites` `Aliases`. However, an AWS CloudFront distribution can only bind **one** ACM certificate (`*.echo9.net`). Attaching custom domain aliases without their certificate on the distribution causes `SSL_ERROR_BAD_CERT_DOMAIN` or `InvalidViewerCertificate`. Additionally, `CLOUDFRONT_SITES_DISTRIBUTION_ID` and `cloudfront:*` IAM permissions were missing from the `9host-api` Lambda, and `tofu apply` overwrote `aliases` on every CI run.
3. **Bare Domain Redirect:** `echo9.net` previously redirected to `tools.e9.cx` instead of serving a `(www.)echo9.net` landing page.

---

## Decision

We adopt a **Split Edge Architecture** combining AWS CloudFront KeyValueStore (KVS) with **Cloudflare for SaaS (Option B2)**:

1. **Split Admin Control Plane from Public Sites Plane:**
   - **Admin SPA Distribution:** `app.echo9.net` (production) and `stage.echo9.net` (staging) serve the React Admin/Superadmin SPA (`S3-9host-frontend-*`) and `/api/*` exclusively.
   - **Public Sites Distribution (`*.echo9.net` + `sites-origin.echo9.net`):** Default behavior (`/*`) points directly to `S3-9host-sites`. Visiting `https://<slug>.echo9.net/` never boots the React SPA and never invokes Lambda or DynamoDB.
   - **Landing Page (`echo9.net` / `www.echo9.net`):** Served as a published site (or dedicated static landing prefix) via the edge router rather than redirecting to `tools.e9.cx`.

2. **CloudFront KeyValueStore (`HostMappingKVS`) in `cf-site-content.js`:**
   - Create `aws_cloudfront_key_value_store.site_hosts` (`9host-site-hosts-kvs`) and associate it with `cf-site-content.js` (`cloudfront-js-2.0`).
   - Whenever a site is published or a custom domain is activated, `SiteStoragePort` writes the mapping:
     - `<site_slug>.echo9.net` -> `{"tenant": "<tenant_slug>", "site_id": "<site_id>"}`
     - `<custom_domain>` -> `{"tenant": "<tenant_slug>", "site_id": "<site_id>"}`
   - On every viewer request, `cf-site-content.js` reads the effective hostname, resolves `{tenant}/{site_id}` from KVS in $<1\text{ ms}$, and rewrites `request.uri` to `/{tenant}/{site_id}/published/current/index.html` at `/`.
   - Delete `RootRoute` from `frontend/src/App.tsx` and delete `api/default_site_handler.py`.

3. **Cloudflare for SaaS (`proxy.echonin9.com`) + Fallback Worker for Custom Domains:**
   - Retire and delete `infra/lambda_acm.tf`, `infra/lambda_acm_handler/main.py`, and all AWS ACM / CloudFront Alias mutation code in `api/custom_domain_handler.py`.
   - Use **Cloudflare for SaaS (Custom Hostnames)** on the `echo9.net` zone (first 100 custom hostnames are **$0/month** on Cloudflare Free plan; $0.10/hostname/month thereafter).
   - End users at ClouDNS or any DNS registrar simply add `CNAME -> proxy.echonin9.com` (plus TXT validation record).
   - Because AWS CloudFront rejects HTTP requests whose `Host` header is not in its `Aliases` list (`403 Forbidden`) and Cloudflare Host Header Override requires an Enterprise plan, deploy a **12-line Cloudflare Worker** on `echo9.net` (Cloudflare Workers Free tier: **100,000 requests/day at $0/month**) as the Custom Hostnames Fallback Origin:
     - The Worker fetches `https://sites-origin.echo9.net${url.pathname}${url.search}` while passing `X-Forwarded-Host: ${url.hostname}` and a shared `X-9host-Edge-Secret` header.
     - `cf-site-content.js` trusts `x-forwarded-host` when `x-9host-edge-secret` matches, and resolves the custom domain in `HostMappingKVS`.

---

## Consequences

- **Positive:**
  - $0/month fixed cost for up to 100 custom domains and 100,000 custom-domain requests/day.
  - Simplest possible UX for end users (1 CNAME record at ClouDNS or any DNS provider).
  - Sub-millisecond static site serving at `/` with clean root-relative URLs (`/`, `/blog/`, `/events/`) and zero Lambda/DynamoDB cost per visitor.
  - Eliminates ~500 lines of brittle ACM polling, EventBridge rules, and CloudFront `UpdateDistribution` calls.
- **Negative / Trade-offs:**
  - Requires `echo9.net` DNS zone to be active on Cloudflare with Custom Hostnames enabled and one Worker deployed (documented step-by-step in `docs/UNATTENDED_ORCHESTRATION.md`).
