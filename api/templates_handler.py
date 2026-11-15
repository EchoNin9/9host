"""
Templates API — GET /api/templates (Task 1.30; T-32a).

Platform templates selectable by the tenant: tier-filtered (tenant.tier >= tier_required), minus
deprecated templates and templates with no published version yet. Sites already on a deprecated
template keep working (publish resolves the template by id). Tenant forks were dropped (ADR-0003
owner answer 6), so they are no longer listed.
"""

from request_context import RequestContext, respond
from tenant_store import DynamoDBTenantStore
from tier_config import tier_rank


def get_templates_handler(ctx: RequestContext) -> dict:
    tenant_slug, _ = ctx.require_tenant_member()
    store = DynamoDBTenantStore()
    tenant = store.get_tenant(tenant_slug)
    if not tenant:
        return respond(404, {"error": "Tenant not found."})
    rank = tier_rank(tenant.get("tier", "FREE"))
    templates = [
        {
            "slug": t["slug"],
            "name": t.get("name") or t["slug"],
            "description": t.get("description", ""),
            "tier_required": t.get("tier_required", "FREE"),
            "base_renderer": t.get("base_renderer") or t["slug"],
            "published_version": t.get("published_version"),
            "components": t.get("components") or {},
        }
        for t in store.list_templates()
        # published_version 0 = created via the admin API, never published (absent = pre-T-32a head)
        if not t.get("deprecated") and t.get("published_version") != 0
        and tier_rank(t.get("tier_required", "FREE")) <= rank
    ]
    return respond(200, {"templates": templates})
