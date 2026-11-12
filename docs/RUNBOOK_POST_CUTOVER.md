# 9host — Post-Cutover Runbook (autonomous, 2026-11-12 →)

For a fresh Commander agent. Read this file, `AGENTS.md`, `CLAUDE.md` and `GLOSSARY.md` first. `docs/UNATTENDED_ORCHESTRATION.md` §6–§7 hold the history and the full ticket specs for `T-13`–`T-19`. This file overrides them where they conflict.

---

## 1. Current state (verified 2026-11-12)

- **Live:** `develop` and `main` are both deployed (PR #17, merge `440f83a`, 2026-11-12). Tasks A–F below are done except A (`jinks.ca` pending); outcomes in §5. **Next run: §7.**
- **Admin SPA:** `app.echo9.net` (prod) and `stage.echo9.net` (staging).
- **Tenant sites:** `*.echo9.net` is served as static HTML by CloudFront `E1P9K5ZO6DTDWR` (`d2nqdv42n1qlhv.cloudfront.net`) via `cf-site-content.js` + KVS `9host-site-hosts-kvs` (`arn:aws:cloudfront::452644920012:key-value-store/10537886-08ea-4b05-87c9-68a1684e6f41`). Unmapped hosts return 404.
- **Admin SPA distributions:** production `E26B25DDJUH6YE` (`d1y8o0nam8q0rq`), alias `app` only (`prod` retired, NXDOMAIN); staging `E1NLQ7KZ99HQJ5` (`d327su5s05gt98`).
- **Landing (staging):** `preview.echo9.net` → CloudFront `EYLR0G6R8Z1BK` (`dggrw8k6efaha.cloudfront.net`), bucket `9host-landing`, synced from `landing/` by CI. Not a tenant site; never in the KVS.
- **Custom domains:** Cloudflare for SaaS on zone `echonin9.com` (fallback origin `proxy.echonin9.com`, Worker `9host-custom-domain-proxy`). Customers point `CNAME`/`ALIAS -> proxy.echonin9.com` plus a `_cf-custom-hostname` TXT.
  - Live: `oliverjinks.com` and `www.oliverjinks.com`.
  - Live: `jinks.ca` (ACTIVE 2026-11-12, KVS key present, 200). `www.jinks.ca` is not configured (no Cloudflare custom hostname, no KVS key).
- **Published sites** (tenant `jinks`). Republished 2026-11-12 with root-relative links:

  | Subdomain | Site ID |
  |---|---|
  | `jinks4` | `80e9d9b4-3695-4bce-bebb-188cb01e8e15` |
  | `jinks-ca` | `8e19335e-8c56-4668-a900-6fff06bc507c` |
  | `oliverjinks-com` | `4ee567a5-e8a7-4164-9bdb-2a2cab21868a` |

- **Baseline checks (all must stay green):**
  - `cd api && ../.venv/bin/pytest -q` (361)
  - `npm --prefix frontend test -- --run` (43)
  - `npm --prefix frontend run build`
  - `node --test infra/tests/*.test.mjs` (21)
  - `scripts/build-lambda-package.sh && AWS_PROFILE=echo9 AWS_REGION=us-east-1 tofu -chdir=infra validate`

## 2. Guardrails (hard rules)

1. **Branches:** work on `develop` only. Commit per ticket as `agent{N} task {T-XX}: ...` with the `Co-Authored-By` trailer from the session. **Never push to or merge into `main`**; the owner merges `develop` → `main` after reviewing staging.
2. **`develop` CI applies the shared OpenTofu state, which includes production infrastructure** (one state for staging and production distributions, Lambda, DynamoDB). Treat every push of a `.tf` change as a production change: plan locally first, and say in the commit message what it changes.
3. **Local tofu:**
   - **Root config:** init with `-backend-config="bucket=9host-tofu-state-452644920012" -backend-config="key=9host/terraform.tfstate" -backend-config="region=us-east-1" -backend-config="dynamodb_table=9host-tofu-state-lock"`, and pass `-var='github_org_repo=EchoNin9/9host' -var='domains=["echo9.net"]'`.
   - **Applying:** `tofu plan -out=<file>`, then `tofu show <file>`, then `tofu apply <file>`. Applies without a reviewed plan are refused by the session's safety checks.
   - **`infra/cloudns`:** state is local and manages only the zone (`T-24`). The `echo9.net` edge records (`app`, `sites-origin`, `tools`, `preview`) are managed by `infra/cloudns/scripts/edge_records.py` (dry run by default; `--apply` to write; the dry run must show the intended change only). Pre-T-24 state backup: `infra/cloudns/terraform.tfstate.pre-T24.backup`.
4. **ClouDNS edits:** allowed only on zone `echo9.net`, and only for the records named in a task. **Never read or edit `jinks.ca`** (owner's personal zone and a real-customer test). Never touch MX/NS/TXT mail records anywhere.
5. **AWS:** `--profile echo9`, `us-east-1`, account `452644920012`. Only modify or delete resources named `9host*` or listed here.
   - Do not touch `E164B9WJ8ALT9F` (landing/other domains), `E1S4CU3NV8WOAL` (URL shortener), or any non-9host distribution or certificate.
   - The local AWS CLI is old and lacks `cloudfront-keyvaluestore`; use boto3 from `.venv` for KVS.
6. **Secrets:**
   - Cloudflare for SaaS credentials are in AWS secret `9host-cloudflare`; ClouDNS in `9host-cloudns`.
   - A Workers-only deploy token is in local `.env.cloudflare` (`CLOUDFLARE_WORKERS_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`).
   - Never print secret values.
7. **Stop and ask the owner** before:
   - anything irreversible not listed here;
   - any change to `echo9.net` / `www.echo9.net` DNS;
   - removing aliases from `E164B9WJ8ALT9F`;
   - anything that would take a live site offline.
8. **Delegation:** the Commander keeps its context lean.
   - Use **Opus** subagents for code tickets (`T-13`, `T-14`, `T-15`, `T-17`, landing site) and **Sonnet** for checks, packaging and reviews.
   - Brief each subagent with exact file ownership, acceptance criteria and test commands. Subagents never commit, never push and never apply infrastructure.
   - The Commander reviews `git diff --stat` plus test output, commits, pushes, and watches CI (`gh run watch <id> --exit-status`), fixing failures until green.

---

## 3. Tasks (do in this order)

### A. Confirm `jinks.ca` activation (read-only)
- Poll the domain row (`TENANT#jinks` / `DOMAIN#jinks.ca`) via `custom_domain_handler.refresh_domain_status` (run from `api/` with env `CLOUDFLARE_SECRET_ARN=9host-cloudflare DOMAINS=echo9.net SITE_HOSTS_KVS_ARN=<KVS ARN>`), until it is `ACTIVE` and the KVS has a `jinks.ca` key.
- Then `curl https://jinks.ca/` should return 200. Allow about 1 minute of 404 after activation while the KVS propagates.
- **Do not change `jinks.ca` DNS.** If it is still pending after 24h, report the `verification_errors` to the owner.

### B. Republish the 3 sites (owner item 2)
- Republish each site above through the app's own publish path in `api/publish_handler.py`; don't hand-write S3 objects.
- **Acceptance:**
  - `published_version` increments.
  - `https://<slug>.echo9.net/` returns 200, and its HTML contains root-relative links (`href="/blog/"`) and no `/site/jinks/`.
  - `oliverjinks.com` still returns 200.
- Invalidate `E1P9K5ZO6DTDWR` `/*` afterwards.

### C. Retire `prod.echo9.net` (owner item 3)
- **Before:** check `app.echo9.net` serves the current bundle and that nothing in the repo (frontend env, Cognito, docs) still points users at `prod`.
- **Changes:**
  - Remove `prod.{d}` from the production distribution aliases and the `aws_acm_certificate.main` SANs in `infra/` (create-before-destroy cert replacement; the `stage` and `app` validation CNAMEs already exist).
  - Remove `https://prod.*` from the Cognito callback and logout URLs.
- **Apply:** plan locally, push to `develop`, watch CI.
- **After CI is green:** delete ClouDNS `echo9.net` records `740575166` (CNAME `prod`) and `740290818` (its ACM validation CNAME) via the API. Verify the IDs and hosts first.
- **Acceptance:** `prod.echo9.net` no longer resolves; `app.echo9.net` and `stage.echo9.net` still return 200 and login works.

### D. `T-19` — post-deploy runtime verification (owner item 4)
- Run the checks in `UNATTENDED_ORCHESTRATION.md` §7 `T-19` against the live stack and append a pass/fail table there:
  - a draft-preview link loads, and a tampered token gets 403;
  - Lambda logs show no `MissingDependencyException` or "falling back to get_user";
  - publishing writes the subdomain KVS key;
  - the Edge & Domains panel hides `__` keys;
  - TUSER site-login, with a manager able to edit.
- Every failure becomes its own `T-2x` ticket, fixed via subagent and pushed to `develop`.
- Browser checks: use the claude-in-chrome tools if available. Otherwise mark those rows "needs owner" — do not guess.

### E. `T-13`–`T-18` — follow-on tickets (owner item 5)
- Implement per `UNATTENDED_ORCHESTRATION.md` §7, one commit and push per ticket, CI green before the next.
- `T-15` starts by proving or disproving the custom-role gap with a failing test.
- **Additions to `T-16`:** fix the ClouDNS provider read bug, either by pinning or upgrading the provider if a fixed version exists, or by moving the three `echo9.net` edge records to an API script. Then drop the `-refresh=false` rule from this file.
- **Additions to `T-18`:**
  - Reserve platform hostnames as tenant site slugs: `app`, `stage`, `prod`, `www`, `tools`, `sites-origin`, `proxy`, `preview`, `api`, `admin`. Enforce it in slug validation (`api/validate_slug_handler.py` and the site create/update path) with a test.
  - Optionally move `CLOUDFLARE_WORKERS_TOKEN` deploys into CI.

### F. Standalone `(www.)echo9.net` landing site (owner item 6)
- **Owner decision 2026-11-11:** the landing page is its own website, not a tenant site. Never map it in the KVS. Keep `serve_landing_domain = false` and `landing_site = null`.
- **Staging URL: `preview.echo9.net`.** It's a specific alias, allowed alongside `*.echo9.net` on another distribution. Reserve `preview` as a slug (task E/`T-18`) before going live.
- **Build:**
  - A small static site, either in a new top-level `landing/` folder (plain HTML/CSS) or a minimal Vite build, using `docs/ui-mockups.html` as the design reference. It must include the `⚡ Echo9 Tools (tools.e9.cx ↗)` button.
  - It must not expose tenant domains, subdomains or KVS entries (SPEC Public Landing Security Rule).
- **Infrastructure:**
  - Add OpenTofu resources: S3 bucket `9host-landing` (private, OAC) and CloudFront distribution `9host-landing` with alias `preview.echo9.net` and the existing `*.echo9.net` wildcard cert.
  - Add a ClouDNS `CNAME preview -> <landing dist>` in `infra/cloudns` (with `-refresh=false`).
  - Add a CI step to sync `landing/` to the bucket and invalidate it.
- **Acceptance:** `https://preview.echo9.net/` returns 200 with the landing page; `tools.e9.cx` button present; no tenant data.
- **STOP after staging.** The production cutover needs the owner, because `echo9.net` / `www.echo9.net` are held by the non-9host distribution `E164B9WJ8ALT9F`:
  - remove those aliases there;
  - add them to `9host-landing` (the apex needs a cert covering `echo9.net`);
  - change ClouDNS `@` (`180304152`) and `www` (`180304155`), currently web redirects to `tools.e9.cx`.
  Write the exact cutover steps into this file and report.
- **Report only, don't fix:** `E164B9WJ8ALT9F` has an **EXPIRED** `echo9.net` certificate (HTTPS broken for `echo9.ca`, `echo9.tech`, `echonin9.com` aliases there).

---

## 4. Definition of done for this runbook
- A–F complete, or blocked with a clear owner question.
- All baseline checks green.
- The last `develop` CI run green.
- `AGENTS.md` ticket checkboxes and this file's task list updated with outcomes and commit SHAs.
- Final report to the owner: what changed in production, what is waiting for them (landing cutover, `develop` → `main` merge), and any new tickets.

---

## 5. Outcomes (2026-11-12, Commander run)

| Task | Outcome | Commits |
|---|---|---|
| A. `jinks.ca` | **Still `PENDING_VALIDATION`** at 07:47 UTC, `verification_errors: []`, no KVS key. Waiting on Cloudflare; re-check with `refresh_domain_status`. Escalate to the owner if still pending 24h after the DNS change. | — |
| B. Republish | Done via `publish_handler._publish_site`. jinks4 v17→18, jinks-ca v1→2, oliverjinks-com v4→5. All 200, root-relative links, no `/site/jinks/`. `oliverjinks.com` 200. Invalidation `IL33NWU7ETAWGB2H75Q4WOQQA`. | — (data only) |
| C. Retire `prod` | Done. Cert replaced without the prod SAN, prod alias removed from `E26B25DDJUH6YE`, Cognito prod URLs removed. ClouDNS `740575166` + `740290818` deleted (owner-approved). `prod.echo9.net` is NXDOMAIN. `app`/`stage` 200, owner verified superadmin login on `app`. | `318938f`, `c75b9bc` |
| D. `T-19` | All automated checks pass (results table in `UNATTENDED_ORCHESTRATION.md` §7). **Needs owner:** Edge & Domains panel in a browser; live manager TUSER login + edit. | `d8c90e2` |
| E. `T-16` | CI test gate (pytest/vitest/build/edge) before AWS creds; CI on Node 22; deploy-role KVS key actions scoped to the KVS ARN (policy compacted to 5986/6144 chars); `tofu fmt`. ClouDNS provider bug **not** fixed upstream → `T-24`. | `e549b3d`, `ce1e516`, `1398c06` |
| E. `T-14` | Atomic `update_site`, S3 prefix cleanup on site/tenant delete, migration marker on tenant create. | `e61f57b` |
| E. `T-13` | All legacy handlers on `RequestContext`; `auth_helpers.py` / `with_tenant` deleted. Auth now runs before input validation (401/403 instead of 400). | `9033b46` |
| E. `T-15` | Gap was real (custom role with `sites` permission got 403). Content routes now honour `permissions.sites`. Other permission keys → `T-23`. | `519e416` |
| E. `T-17` | Tenants/domains get `gsi3` `ENTITY#…` keys; superadmin lists query instead of scan; CI backfill step. | `f26969b` |
| E. `T-18` | Reserved slugs (`api/reserved_slugs.py`), platform hosts incl. `app.`, link `rel`, Cloudflare poll throttle, console polish. **Edge-function part reverted:** the new `cf-site-content.js` threw `FunctionExecutionError` in the real runtime and all tenant sites returned **503 for ~15 min** (07:30–07:45 UTC) → `T-21`. Production `/media/*` behaviour not done (needs `.tf`) → `T-22`. | `53a27b4`, `3394394`, `aa3ad44` |
| `T-20` (new, owner) | Platform admins listed in their own section of the superadmin Users console; Lambda gets `cognito-idp:ListUsersInGroup`. | `7d2c0d4` |
| F. Landing | Live at `https://preview.echo9.net/` (CloudFront `EYLR0G6R8Z1BK` / `dggrw8k6efaha.cloudfront.net`, bucket `9host-landing`). 200, tools.e9.cx button, custom 404, no tenant data. ClouDNS `preview` CNAME applied with `-target`. **Production cutover waits for the owner** (§6). | `7eeb732` |

### New tickets
- `T-21`: Re-land the `X-Forwarded-Host` proxy-secret check in `cf-site-content.js` (code in `53a27b4`). First find the runtime error with `aws cloudfront test-function` against the DEVELOPMENT stage; add a CI step that runs `test-function` before the function is published. Then the Worker secret + `__proxy_secret__` KVS key rollout (order in the `53a27b4` report: Worker secret → Worker deploy → KVS key).
- `T-22`: Add the `/media/*` cache behaviour to the production Admin SPA distribution (staging has it).
- `T-23`: Enforce the remaining CustomRole permission keys (`domains`, `analytics`, `settings`, `users`) server-side.
- `T-24`: ClouDNS provider read bug (`retrec.priority` string vs number, unfixed in 1.3.3): upstream fix to `cloudns-go`, or move the `echo9.net` edge records to an API script and keep only the zone in tofu.
- `T-25` (owner, report only): `E164B9WJ8ALT9F` has an **expired** `echo9.net` certificate; HTTPS is broken for its `echo9.ca`, `echo9.tech`, `echonin9.com` aliases.
- `T-26` (owner decision): Align the Admin SPA with `docs/ui-mockups.html` screens 2–4. Today it matches the information architecture only: shadcn/teal theme vs the mockup's dark/coral/Geist (L); Sites cards lack live URLs, version, inline Publish/Rollback (M); sidebar tenant-switcher card (M); domains as a single status table (M); superadmin edge kvs grid + Cognito/TUSER cards (M). The landing page (screen 1) already matches. Keep `proxy.echonin9.com` (the mockup's `proxy.echo9.net` is wrong).

## 6. Landing production cutover (owner-run; do not automate)

The wildcard cert (`aws_acm_certificate.wildcard`) already includes the `echo9.net` apex, and `www` is covered by `*.echo9.net`. No cert change is needed.

1. **Pre-checks:**
   - The wildcard cert is `ISSUED` with SANs `*.echo9.net` and `echo9.net`.
   - `https://preview.echo9.net/` returns 200.
   - `preview` is reserved (done in `T-18`).
2. **Remove `echo9.net` and `www.echo9.net` from `E164B9WJ8ALT9F`:**
   - `get-distribution-config`, edit `Aliases`, then `update-distribution --if-match <ETag>`, and wait for `Deployed`.
   - Its cert is expired, so the update may be rejected (`InvalidViewerCertificate`). If so, attach a valid cert for its remaining aliases in the same update.
   - There's no visitor impact: those names are currently ClouDNS web redirects, not pointed at that distribution.
3. **Add the aliases to `9host-landing`:**
   - In `infra/landing.tf`, add `echo9.net` and `www.echo9.net` to the landing aliases.
   - Keep `serve_landing_domain = false` and `landing_site = null`.
   - Plan locally (expect only an in-place `aws_cloudfront_distribution.landing` alias change), then push to `develop`.
   - `CNAMEAlreadyExists` means step 2 isn't finished.
4. **Update ClouDNS (`echo9.net` only):**
   - Verify `180304152` = `@` WR and `180304155` = `www` WR.
   - Delete `180304152`, then add an `ALIAS @ -> dggrw8k6efaha.cloudfront.net` (TTL 300).
   - Delete `180304155`, then add a `CNAME www -> dggrw8k6efaha.cloudfront.net`.
   - Do each delete and add back to back. Leave `tools` alone.
5. **Verify:**
   - `echo9.net` and `www.echo9.net` return 200 with the landing page and the tools button.
   - `tools.echo9.net` still returns 301.
   - Tenant subdomains still work.
   - Invalidate `EYLR0G6R8Z1BK` `/*`.
6. **Rollback:**
   - Recreate the WR records `@` and `www` -> `https://tools.e9.cx` (301).
   - The aliases can stay on the landing distribution.

## 7. Next run (fresh Commander, from 2026-11-13)

Same guardrails (§2) and workflow: one commit + push to `develop` per ticket, CI green before the next, never push to `main`. Run the baseline checks (§1) first; expected counts now: pytest 337, vitest 43, edge 19.

Order and acceptance:
1. **A carry-over: `jinks.ca`.** Poll as in §3 A. If `ACTIVE`, confirm the KVS key and that `https://jinks.ca/` returns 200. If still pending, report `verification_errors` and do not touch its DNS.
2. **`T-21` edge proxy-secret check** (Opus).
   - Start from the reverted code in `53a27b4` (`git show 53a27b4 -- infra/cf-site-content.js infra/tests/edge-functions.test.mjs`).
   - Find the runtime error that made every request 503. Reproduce it with `aws cloudfront test-function` on a scratch function `9host-site-content-t21` (create, test, delete). **Never `update-function` / `publish-function` the live `9host-site-content`.** CI deploys it.
   - Add a CI step that runs `test-function` against the DEVELOPMENT stage before the publishing apply. The deploy role must allow `cloudfront:TestFunction`; watch the 6144-char policy limit (currently ~6060).
   - Acceptance:
     - `test-function` returns 200 / a rewritten URI for a mapped host, and 404 for an unmapped one.
     - After pushing, `jinks4.echo9.net`, `oliverjinks.com` and `www.oliverjinks.com` return 200 within 5 minutes. Otherwise revert immediately by git revert + push (revert the tests too, or the CI gate blocks the revert).
   - Leave the Worker secret, `wrangler deploy` and the `__proxy_secret__` KVS key to the owner. Write the exact commands in this file.
3. **`T-22` production `/media/*` behaviour** (Opus).
   - Mirror the staging distribution's `/media/*` ordered cache behaviour onto `aws_cloudfront_distribution.production` in `infra/cloudfront.tf`.
   - Plan locally: only an in-place update of `E26B25DDJUH6YE`, plus Lambda hash noise.
   - Acceptance: `curl -sI https://app.echo9.net/media/<existing key>` returns the same as on `stage`.
4. **`T-23` remaining CustomRole permissions** (Opus).
   - Use `RequestContext.require_permission(module, roles)` (from `T-15`) on the domains, analytics, settings and users routes, with the same semantics: built-in roles are unchanged, and custom roles need `permissions[module] is True`.
   - Acceptance: tests in `api/tests/test_custom_roles.py` for each key (granted gets 2xx, absent gets 403); built-in role behaviour unchanged.
5. **`T-24` ClouDNS records** (Opus).
   - Preferred: move the `echo9.net` edge records (`app`, `sites-origin`, `tools`, `preview`) out of OpenTofu.
     - `tofu state rm` them in `infra/cloudns`, after backing up `terraform.tfstate`.
     - Add an idempotent `infra/cloudns/scripts/edge_records.py` that reads targets from root `tofu output` and upserts them through the ClouDNS API (secret `9host-cloudns`).
     - Keep only the zone in tofu.
   - The script's dry run must show **no changes** against live DNS before any real run. Never touch `jinks.ca`, `@`, `www`, or MX/NS/TXT records.
   - Then remove the `-refresh=false` / `-target` rule from §2.3.
6. **Owner-only, do not do:**
   - `T-25` (expired cert on `E164B9WJ8ALT9F`).
   - `T-26` (Admin SPA restyle to the mockups; wait for the owner's go-ahead).
   - The §6 landing production cutover.

Finish by updating §5 / `AGENTS.md` with outcomes and SHAs, and reporting what changed in production and what is waiting on the owner.

### §7 status (2026-11-12, second Commander run)

Items 1–5 done; item 6 untouched (owner). Every push was green in develop CI, and after each one `jinks4.echo9.net`, `oliverjinks.com`, `www.oliverjinks.com`, `app.echo9.net`, `preview.echo9.net` returned 200.

| Item | Outcome | Commit |
|---|---|---|
| 1. `jinks.ca` | `ACTIVE`, `verification_errors: []`, KVS key present, `https://jinks.ca/` 200 (first curl 404 during KVS propagation). `www.jinks.ca` not configured — owner decision. | — |
| 2. `T-21` | Root cause of the T-18 503: cloudfront-js-2.0 rejects `await` inside call arguments (`String(await kvsHandle.get(...))`) with a load-time SyntaxError; Node accepts it. Fixed (await only as a plain assignment), proven with `test-function` on scratch `9host-site-content-t21` (deleted). Fails open while `__proxy_secret__` is absent (today). CI now runs `infra/tests/cf_test_function.py` (DEVELOPMENT stage, mapped + unmapped host) before apply; deploy policy gained `cloudfront:TestFunction` (6072/6144 chars). New edge tests incl. a static `await`-placement guard. LIVE published 11:29 UTC, all sites 200. The commit also carries T-24's deletion of `infra/cloudns/scripts/import-existing-records.sh`. | `5f088e4` |
| 3. `T-22` | Production `E26B25DDJUH6YE` has the `/media/*` origin + behaviour; media bucket policy allows it. `app` and `stage` both return 200 `binary/octet-stream` 980813 bytes for `/media/jinks/80e9d9b4-…/014445eb-joshing-logo1.png` (app was 403). | `55de689` |
| 4. `T-23` | `require_permission` on domains (POST/DELETE/activate), analytics (GET), settings (PATCH `/api/tenant`), users (`/api/tenant/users`, `/api/tenant/tusers`). Escalation guard: `/api/tenant/roles` stays built-in admin/manager only; custom-role callers may assign only `member`/`editor` to TUSERs. Built-in roles unchanged. pytest 361. | `f068e73` |
| 5. `T-24` | `infra/cloudns` manages only the zone; edge records via `infra/cloudns/scripts/edge_records.py` (dry run 0 changes vs live DNS; never applied). State backup `infra/cloudns/terraform.tfstate.pre-T24.backup`. §2.3 updated. | `b9b544f` |

#### Owner: `T-21` proxy-secret rollout (only while all sites are 200)
Run from the repo root, in one shell.
1. Deploy the Worker (already sends `X-9host-Proxy-Secret` only when `PROXY_SECRET` is set, so harmless):
   `set -a; . ./.env.cloudflare; set +a; export CLOUDFLARE_API_TOKEN="$CLOUDFLARE_WORKERS_TOKEN"; (cd infra/cloudflare-worker && npx wrangler deploy)` — rollback `npx wrangler rollback`.
2. Set the secret: `export PROXY_SECRET="$(openssl rand -hex 32)"; (cd infra/cloudflare-worker && printf %s "$PROXY_SECRET" | npx wrangler secret put PROXY_SECRET)` — rollback `npx wrangler secret delete PROXY_SECRET` (delete the KVS key first if written).
3. Write the KVS key (enforcement starts):
   `.venv/bin/python -c "import os,boto3;c=boto3.Session(profile_name='echo9',region_name='us-east-1').client('cloudfront-keyvaluestore');a='arn:aws:cloudfront::452644920012:key-value-store/10537886-08ea-4b05-87c9-68a1684e6f41';c.put_key(KvsARN=a,Key='__proxy_secret__',Value=os.environ['PROXY_SECRET'],IfMatch=c.describe_key_value_store(KvsARN=a)['ETag']);print('ok')"; unset PROXY_SECRET`
   Verify: `oliverjinks.com` and `www.oliverjinks.com` 200; `curl -s -o /dev/null -w '%{http_code}' -H 'X-Forwarded-Host: oliverjinks.com' https://sites-origin.echo9.net/` → 404.
   Rollback (instant): same snippet with `c.delete_key(KvsARN=a,Key='__proxy_secret__',IfMatch=...)`.

#### New notes / tickets
- `T-27`: owner decision 2026-11-12 — drop the built-in `editor` role (in progress).
- `T-28`: The CI test-function gate uses `jinks4.echo9.net` as its mapped host; change `--mapped-host` in `cf_test_function.py` if that site is ever removed.
- `www.jinks.ca`: add a Cloudflare custom hostname + KVS key if wanted (owner).

### Follow-up tickets (owner, 2026-11-12)
Main merged from develop (PR #18) after owner review of stage + preview.

- `T-29` **Landing showcase redesign.** `landing/` (preview.echo9.net, later echo9.net) is good enough for now but not showcase quality. Redesign with high-quality design skills (design-director / artifact-design level polish): typography, hierarchy, imagery, motion, responsive, dark mode. Keep the `⚡ Echo9 Tools (tools.e9.cx ↗)` button and the SPEC Public Landing Security Rule (no tenant data). Plain static output synced by CI.
- `T-30` **Admin SPA redesign (app/stage).** Current UX is awkward and the UI is ugly. Audit flows (sites, publish, pages/posts/events/media, domains, users, superadmin console), then redesign navigation, layout and visual system on shadcn/Tailwind. Supersedes `T-26` (mockups in `docs/ui-mockups.html` are a starting reference, not a spec). Owner reviews on stage before main.
- `T-31` **WYSIWYG templates.** Refactor the site templates system (`api/templates/`, `SiteCompiler`) so tenants edit pages visually in a WYSIWYG editor that round-trips to the compiled static HTML. Must keep `compile_site` pure, HTML sanitization, root-relative links, and draft preview. Needs a design spike (editor library, content model/migration) before code.
- `T-32` **WYSIWYG template admin.** Refactor the superadmin template admin section into a WYSIWYG interface for creating/editing platform templates; depends on `T-31`'s content model.
