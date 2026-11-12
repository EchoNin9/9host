"""
Site rollback API (Task 1.96b).

POST /api/tenant/sites/{id}/rollback?version=N — admin/manager. Copies v{N}/ to current/,
repoints current.json and updates the Site via publish_handler._rollback_site (SiteStoragePort).
"""

from publish_handler import MANAGE_ROLES, _rollback_site, _s3, load_site
from request_context import RequestContext, respond


def rollback_handler(ctx: RequestContext) -> dict:
    store, tenant_slug, site_id, _ = load_site(ctx, "rollback", MANAGE_ROLES)
    version_str = ctx.query("version")
    if not version_str.isdigit():
        return respond(400, {"error": "Query parameter version=N is required (integer)."})
    version = int(version_str)
    if version < 1:
        return respond(400, {"error": "Version must be >= 1."})
    result = _rollback_site(store.table, _s3(), tenant_slug, site_id, version)
    if result is None:
        return respond(404, {"error": f"Version {version} not found. No published v{version}."})
    return respond(200, {"rollback": result})
