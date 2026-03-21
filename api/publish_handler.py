"""
Site publish API (Task 1.96, 1.109, 1.115).

POST /api/tenant/sites/{id}/publish — atomic versioned publish:
  render HTML from template + content → upload to published/v{N}/ →
  copy to current/ → manifest.json → current.json → update Site.

Task 1.109: Template-aware rendering — components, sections, /blog/, /posts/{slug}/,
/events/, branding injection.
Task 1.111: Wire media URLs as /media/{tenant}/{site}/{filename} in rendered HTML.
Task 1.115: Use template renderer system (api/templates/) with per-template CSS themes.
"""

import hashlib
import json
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError as BotoClientError

from auth_helpers import require_tenant_admin_or_manager, require_tenant_auth, role_can_upload, role_is_admin_or_manager
from dynamodb_helpers import (
    get_site_item,
    get_template_item,
    get_tenant_item,
    get_tenant_template_item,
    pk_tenant,
)
from middleware import with_tenant
from path_utils import site_base_path
from templates import get_renderer
from templates.base_layout import escape_html, media_url
from tier_config import CONTENT_MODULE_KEYS, FEATURE_KEYS, tier_has_feature, tier_has_module

S3_SITES_BUCKET = "9host-sites"
S3_MEDIA_BUCKET = "9host-media"
HTML_CACHE_CONTROL = "max-age=60, s-maxage=300"
ASSET_CACHE_CONTROL = "max-age=31536000, immutable"


def _json_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _collect_content(table, tenant_slug: str, site_id: str, published_only: bool = True) -> dict:
    """Fetch site content from DynamoDB.

    Args:
        published_only: If True, only include items with status=PUBLISHED.
                       If False, include all items (for draft preview).
    """
    pages = []
    posts = []
    events = []
    media = []

    for entity in ("PAGE", "POST", "EVENT", "MEDIA"):
        params = {
            "KeyConditionExpression": "pk = :pk AND begins_with(sk, :sk)",
            "ExpressionAttributeValues": {
                ":pk": pk_tenant(tenant_slug),
                ":sk": f"SITE#{site_id}#{entity}#",
            },
        }
        resp = table.query(**params)
        for item in resp.get("Items", []):
            # Media items are uploaded assets — no draft/published lifecycle
            if published_only and entity != "MEDIA" and (item.get("status") or "").upper() != "PUBLISHED":
                continue
            if entity == "PAGE":
                pages.append({
                    "path": item.get("path", ""),
                    "title": item.get("title", ""),
                    "body": item.get("body", ""),
                })
            elif entity == "POST":
                posts.append({
                    "slug": item.get("slug", ""),
                    "title": item.get("title", ""),
                    "body": item.get("body", ""),
                    "excerpt": item.get("excerpt", ""),
                    "featured_image_s3_key": item.get("featured_image_s3_key", ""),
                })
            elif entity == "EVENT":
                events.append({
                    "title": item.get("title", ""),
                    "event_date": item.get("event_date", ""),
                    "venue": item.get("venue", ""),
                })
            elif entity == "MEDIA":
                media.append({
                    "s3_key": item.get("s3_key", ""),
                    "caption": item.get("caption", ""),
                })

    return {"pages": pages, "posts": posts, "events": events, "media": media}


def _get_next_version(s3_client, bucket: str, prefix: str) -> int:
    """Determine next version number from existing v* folders or current.json."""
    try:
        obj = s3_client.get_object(Bucket=bucket, Key=f"{prefix}published/current.json")
        data = json.loads(obj["Body"].read().decode())
        return int(data.get("version", 0)) + 1
    except Exception:
        pass

    # List published/ prefix for v* folders
    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        max_v = 0
        for page in paginator.paginate(Bucket=bucket, Prefix=f"{prefix}published/", Delimiter="/"):
            for p in page.get("CommonPrefixes", []):
                name = p["Prefix"].rstrip("/").split("/")[-1]
                if name.startswith("v") and name[1:].isdigit():
                    max_v = max(max_v, int(name[1:]))
        return max_v + 1
    except Exception:
        return 1


def _upload_and_copy(
    s3_client,
    bucket: str,
    tenant_slug: str,
    site_id: str,
    version: int,
    files: dict,
    is_default: bool,
) -> list:
    """
    Upload files to v{N}/, copy to current/, optionally to default/.
    Returns list of (path, sha256, size) for manifest.
    """
    base = f"{tenant_slug}/{site_id}"
    v_prefix = f"{base}/published/v{version}/"
    current_prefix = f"{base}/published/current/"
    default_prefix = f"{tenant_slug}/default/"
    manifest_entries = []

    for path, content in files.items():
        body = content.encode("utf-8") if isinstance(content, str) else content
        sha = hashlib.sha256(body).hexdigest()
        size = len(body)
        manifest_entries.append({"path": path, "sha256": sha, "size": size})

        # Upload to v{N}/
        key_v = f"{v_prefix}{path}"
        if path.endswith(".html"):
            content_type = "text/html; charset=utf-8"
            cache_control = HTML_CACHE_CONTROL
        elif path.endswith(".css"):
            content_type = "text/css; charset=utf-8"
            cache_control = ASSET_CACHE_CONTROL
        elif path.endswith(".xml"):
            content_type = "application/xml; charset=utf-8"
            cache_control = HTML_CACHE_CONTROL
        elif path.endswith(".txt"):
            content_type = "text/plain; charset=utf-8"
            cache_control = HTML_CACHE_CONTROL
        else:
            content_type = "application/octet-stream"
            cache_control = ASSET_CACHE_CONTROL
        s3_client.put_object(
            Bucket=bucket,
            Key=key_v,
            Body=body,
            ContentType=content_type,
            CacheControl=cache_control,
        )

        # Copy to current/
        key_current = f"{current_prefix}{path}"
        s3_client.copy_object(
            Bucket=bucket,
            CopySource={"Bucket": bucket, "Key": key_v},
            Key=key_current,
            CacheControl=cache_control,
        )

        # If default site, copy to default/
        if is_default:
            key_default = f"{default_prefix}{path}"
            s3_client.copy_object(
                Bucket=bucket,
                CopySource={"Bucket": bucket, "Key": key_v},
                Key=key_default,
                CacheControl=cache_control,
            )

    return manifest_entries


def _resolve_features(tenant_item: dict) -> dict:
    """Compute resolved_features from tenant tier + module_overrides (Task 1.122)."""
    tier = (tenant_item.get("tier") or "FREE").upper()
    mo = tenant_item.get("module_overrides") or {}
    out = {}
    for fk in FEATURE_KEYS:
        out[fk] = bool(mo[fk]) if fk in mo else tier_has_feature(tier, fk)
    for mk in CONTENT_MODULE_KEYS:
        out[mk] = bool(mo[mk]) if mk in mo else tier_has_module(tier, mk)
    return out


def _publish_site(
    table,
    s3_client,
    tenant_slug: str,
    site_id: str,
    site_item: dict,
    template_item: dict,
    media_base: str,
    resolved_features: dict | None = None,
) -> dict:
    """Perform the publish flow (Task 1.109, 1.111, 1.115, 1.115a, 1.122, 1.125: template-aware, tenant templates)."""
    # Use forked_from for renderer selection; forked templates inherit base layout
    base_slug = (template_item.get("forked_from") or template_item.get("slug") or "").strip().lower()
    renderer = get_renderer(base_slug)
    if not renderer:
        renderer = get_renderer("business-generic")
    if not renderer:
        raise ValueError(f"No renderer for template: {base_slug}")

    features = resolved_features or {}
    has_blog = features.get("updates_blog", True)
    has_events = features.get("events_shows", True)
    has_branding = features.get("branding", True)

    site_name = site_item.get("name", "Site")
    branding = (
        site_item.get("branding") if has_branding and isinstance(site_item.get("branding"), dict) else {}
    )
    content = _collect_content(table, tenant_slug, site_id, published_only=True)
    pages = content["pages"]
    posts = content["posts"] if has_blog else []
    events = content["events"] if has_events else []
    # Media: always publish if items exist (tier gating is enforced in admin UI upload, not at publish)
    media = content["media"]

    from templates.base_layout import nav_links

    # Task 1.108a: site_base prefix for all internal links so they work under /site/{tenant}/{site_id}/
    site_base = site_base_path(tenant_slug, site_id)
    nav = nav_links(pages, bool(posts), bool(events), bool(media), site_base=site_base)

    # Build files to publish (Task 1.115: template renderer + style.css)
    files = {}

    # style.css (template theme)
    files["style.css"] = renderer.render_css()

    # index.html (base_path="" for root) — meta for SEO (Task 1.128)
    meta_image = media_url(branding.get("logo_s3_key", ""), media_base) if branding and branding.get("logo_s3_key") else ""
    files["index.html"] = renderer.render_index(
        site_name, pages, posts, events, branding, media_base, bool(media), base_path="",
        meta_description=site_name, meta_image=meta_image, site_base=site_base,
    )

    # Per-page HTML
    for p in pages:
        path = p.get("path", "").strip()
        if not path:
            continue
        base_path = "../"  # one level down
        html = renderer.render_page(
            p["path"], p["title"], p["body"], site_name, branding, media_base, nav,
            tenant_slug, site_id, base_path=base_path,
        )
        files[f"{path}/index.html"] = html

    # /blog/ (posts index)
    if posts:
        files["blog/index.html"] = renderer.render_blog_index(
            site_name, posts, branding, media_base, nav, base_path="../", site_base=site_base,
        )

    # /posts/{slug}/ (post detail)
    for post in posts:
        slug = (post.get("slug") or "").strip()
        if slug:
            files[f"posts/{slug}/index.html"] = renderer.render_post_detail(
                post, site_name, branding, media_base, nav,
                tenant_slug, site_id, base_path="../../"
            )

    # /events/
    if events:
        files["events/index.html"] = renderer.render_events(
            site_name, events, branding, media_base, nav, base_path="../"
        )

    # /gallery/
    if media:
        files["gallery/index.html"] = renderer.render_gallery(
            site_name, media, branding, media_base, nav, base_path="../"
        )

    # 404 page (Task 1.127)
    files["404.html"] = renderer.render_404(site_name, branding, media_base, nav, base_path="", site_base=site_base)

    # SEO (Task 1.128): sitemap.xml, robots.txt
    domains = (os.environ.get("DOMAINS") or "echo9.net").split(",")
    base_domain = domains[0].strip() if domains else "echo9.net"
    site_slug = (site_item.get("slug") or "").strip() or "site"
    base_url = f"https://{site_slug}.{base_domain}"
    urls = [base_url + "/"]
    for p in pages:
        path = (p.get("path") or "").strip()
        if path:
            urls.append(f"{base_url}/{path}/")
    if posts:
        urls.append(f"{base_url}/blog/")
        for post in posts:
            slug = (post.get("slug") or "").strip()
            if slug:
                urls.append(f"{base_url}/posts/{slug}/")
    if events:
        urls.append(f"{base_url}/events/")
    if media:
        urls.append(f"{base_url}/gallery/")
    sitemap_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for u in urls:
        sitemap_lines.append(f"  <url><loc>{escape_html(u)}</loc></url>")
    sitemap_lines.append("</urlset>")
    files["sitemap.xml"] = "\n".join(sitemap_lines)
    files["robots.txt"] = f"User-agent: *\nAllow: /\nSitemap: {base_url}/sitemap.xml\n"

    base = f"{tenant_slug}/{site_id}"
    version = _get_next_version(s3_client, S3_SITES_BUCKET, f"{base}/")

    # Check if this is the default site (first published site for tenant)
    try:
        s3_client.head_object(Bucket=S3_SITES_BUCKET, Key=f"{tenant_slug}/default.json")
        is_default = False
    except Exception:
        is_default = True

    manifest_entries = _upload_and_copy(
        s3_client, S3_SITES_BUCKET, tenant_slug, site_id, version, files, is_default
    )

    now = datetime.now(timezone.utc).isoformat()
    manifest = {
        "version": version,
        "published_at": now,
        "files": manifest_entries,
    }

    # Upload manifest to v{N}/
    manifest_key = f"{base}/published/v{version}/manifest.json"
    s3_client.put_object(
        Bucket=S3_SITES_BUCKET,
        Key=manifest_key,
        Body=json.dumps(manifest),
        ContentType="application/json",
    )

    # Write current.json (atomic pointer)
    current_data = {
        "version": version,
        "published_at": now,
        "manifest": f"v{version}/manifest.json",
    }
    current_key = f"{base}/published/current.json"
    s3_client.put_object(
        Bucket=S3_SITES_BUCKET,
        Key=current_key,
        Body=json.dumps(current_data),
        ContentType="application/json",
    )

    # If default, write default.json
    if is_default:
        default_data = {"site_id": site_id, "published_at": now}
        s3_client.put_object(
            Bucket=S3_SITES_BUCKET,
            Key=f"{tenant_slug}/default.json",
            Body=json.dumps(default_data),
            ContentType="application/json",
        )

    # Update Site record
    table.update_item(
        Key=get_site_item(tenant_slug, site_id),
        UpdateExpression="SET #status = :status, published_at = :now, published_version = :ver, updated_at = :now",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": "published",
            ":now": now,
            ":ver": version,
        },
    )

    return {
        "version": version,
        "published_at": now,
        "files_count": len(files),
        "is_default": is_default,
    }


def _draft_publish_site(
    table,
    s3_client,
    tenant_slug: str,
    site_id: str,
    site_item: dict,
    template_item: dict,
    media_base: str,
    resolved_features: dict | None = None,
) -> dict:
    """Render draft HTML to S3 draft/ prefix (Task 1.116, 1.122, 1.125). No versioning."""
    base_slug = (template_item.get("forked_from") or template_item.get("slug") or "").strip().lower()
    renderer = get_renderer(base_slug)
    if not renderer:
        renderer = get_renderer("business-generic")
    if not renderer:
        raise ValueError(f"No renderer for template: {base_slug}")

    features = resolved_features or {}
    has_blog = features.get("updates_blog", True)
    has_events = features.get("events_shows", True)
    has_branding = features.get("branding", True)

    site_name = site_item.get("name", "Site")
    branding = (
        site_item.get("branding") if has_branding and isinstance(site_item.get("branding"), dict) else {}
    )
    content = _collect_content(table, tenant_slug, site_id, published_only=False)
    pages = content["pages"]
    posts = content["posts"] if has_blog else []
    events = content["events"] if has_events else []
    # Media: always include if items exist (tier gating is enforced in admin UI upload, not at publish)
    media = content["media"]

    from templates.base_layout import nav_links

    site_base = "/preview"
    nav = nav_links(pages, bool(posts), bool(events), bool(media), site_base=site_base)

    # Script to propagate ?token= to all nav links so sub-page navigation works
    _TOKEN_SCRIPT = """<script>
(function(){var t=new URLSearchParams(location.search).get("token");if(t){document.querySelectorAll("a[href]").forEach(function(a){try{var u=new URL(a.href,location.origin);if(u.origin===location.origin&&u.pathname.startsWith("/preview")){u.searchParams.set("token",t);a.href=u.pathname+u.search}}catch(e){}})}})();
</script>"""

    # Inline CSS for draft: replace <link stylesheet> with <style> block
    # because /preview/style.css can't be loaded without a token in the URL.
    css_content = renderer.render_css()
    import re
    def _inline_css(html: str) -> str:
        return re.sub(
            r'<link\s+rel="stylesheet"\s+href="[^"]*style\.css">',
            f"<style>\n{css_content}\n</style>",
            html,
        )

    def _draft_html(html: str) -> str:
        return _inline_css(html) + _TOKEN_SCRIPT

    files = {}
    files["index.html"] = _draft_html(renderer.render_index(
        site_name, pages, posts, events, branding, media_base, bool(media), base_path="",
        site_base=site_base,
    ))

    for p in pages:
        path = p.get("path", "").strip()
        if not path:
            continue
        html = renderer.render_page(
            p["path"], p["title"], p["body"], site_name, branding, media_base, nav,
            tenant_slug, site_id, base_path="../",
        )
        files[f"{path}/index.html"] = _draft_html(html)

    if posts:
        files["blog/index.html"] = _draft_html(renderer.render_blog_index(
            site_name, posts, branding, media_base, nav, base_path="../",
            site_base=site_base,
        ))
    for post in posts:
        slug = (post.get("slug") or "").strip()
        if slug:
            files[f"posts/{slug}/index.html"] = _draft_html(renderer.render_post_detail(
                post, site_name, branding, media_base, nav,
                tenant_slug, site_id, base_path="../../"
            ))

    if events:
        files["events/index.html"] = _draft_html(renderer.render_events(
            site_name, events, branding, media_base, nav, base_path="../"
        ))
    if media:
        files["gallery/index.html"] = _draft_html(renderer.render_gallery(
            site_name, media, branding, media_base, nav, base_path="../"
        ))

    files["404.html"] = _draft_html(renderer.render_404(site_name, branding, media_base, nav, base_path="",
                                                         site_base=site_base))

    draft_prefix = f"{tenant_slug}/{site_id}/draft/"
    for path, content in files.items():
        body = content.encode("utf-8") if isinstance(content, str) else content
        key = f"{draft_prefix}{path}"
        if path.endswith(".html"):
            content_type = "text/html; charset=utf-8"
            cache_control = "no-cache, no-store, must-revalidate"
        elif path.endswith(".css"):
            content_type = "text/css; charset=utf-8"
            cache_control = "no-cache, no-store, must-revalidate"
        else:
            content_type = "application/octet-stream"
            cache_control = "no-cache"
        s3_client.put_object(
            Bucket=S3_SITES_BUCKET,
            Key=key,
            Body=body,
            ContentType=content_type,
            CacheControl=cache_control,
        )

    return {"files_count": len(files)}


@with_tenant
def draft_publish_handler(event: dict, context: dict) -> dict:
    """
    POST /api/tenant/sites/{id}/draft-publish — render draft to S3 draft/ (Task 1.116).
    Admin/manager/editor only.
    """
    tenant_slug = event.get("tenant_slug")
    if not tenant_slug:
        return _json_response(400, {"error": "Missing tenant."})

    path = (event.get("rawPath") or event.get("path") or "").rstrip("/")
    prefix = "/api/tenant/sites/"
    suffix = "/draft-publish"
    if not path.startswith(prefix) or not path.endswith(suffix):
        return _json_response(404, {"error": "Not found."})
    site_id = path[len(prefix) : -len(suffix)].strip("/")
    if not site_id:
        return _json_response(400, {"error": "Missing site_id."})

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)
    region = os.environ.get("AWS_REGION", "us-east-1")
    s3_client = boto3.client("s3", region_name=region)

    auth_result = require_tenant_auth(event, table, tenant_slug, region)
    if auth_result[0] is not True:
        _, err_resp = auth_result
        return _json_response(err_resp.get("statusCode", 401), json.loads(err_resp.get("body", "{}")))
    _, sub_or_username, role, is_cognito = auth_result

    if is_cognito:
        if not role_can_upload(role):
            return _json_response(403, {"error": "Editor, manager, or admin role required."})
    elif not role_can_upload(role or ""):
        return _json_response(403, {"error": "Editor, manager, or admin role required."})

    site_key = get_site_item(tenant_slug, site_id)
    site_resp = table.get_item(Key=site_key)
    site_item = site_resp.get("Item")
    if not site_item:
        return _json_response(404, {"error": "Site not found."})

    template_id = (site_item.get("template_id") or "").strip().lower()
    if not template_id:
        return _json_response(400, {"error": "Site has no template_id."})

    template_resp = table.get_item(Key=get_tenant_template_item(tenant_slug, template_id))
    template_item = template_resp.get("Item")
    if not template_item:
        template_resp = table.get_item(Key=get_template_item(template_id))
        template_item = template_resp.get("Item")
    if not template_item:
        return _json_response(404, {"error": f"Template not found: {template_id}"})

    tenant_resp = table.get_item(Key=get_tenant_item(tenant_slug))
    tenant_item = tenant_resp.get("Item") or {}
    resolved_features = _resolve_features(tenant_item)

    media_base = os.environ.get("CLOUDFRONT_MEDIA_URL", "/media/")

    try:
        result = _draft_publish_site(
            table, s3_client, tenant_slug, site_id, site_item, template_item, media_base, resolved_features
        )
        return _json_response(200, {"draft": result})
    except BotoClientError as e:
        return _json_response(500, {"error": "Draft publish failed.", "detail": str(e)})


@with_tenant
def publish_handler(event: dict, context: dict) -> dict:
    """
    POST /api/tenant/sites/{id}/publish — publish site (Task 1.96).
    Admin/manager only.
    """
    tenant_slug = event.get("tenant_slug")
    if not tenant_slug:
        return _json_response(400, {"error": "Missing tenant. Use subdomain or X-Tenant-Slug header."})

    path = (event.get("rawPath") or event.get("path") or "").rstrip("/")
    prefix = "/api/tenant/sites/"
    if not path.startswith(prefix) or "/publish" not in path:
        return _json_response(404, {"error": "Not found."})

    rest = path[len(prefix) :].strip("/")
    parts = rest.split("/")
    if len(parts) != 2 or parts[1] != "publish":
        return _json_response(404, {"error": "Not found."})
    site_id = parts[0]
    if not site_id:
        return _json_response(400, {"error": "Missing site_id."})

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)
    region = os.environ.get("AWS_REGION", "us-east-1")
    s3_client = boto3.client("s3", region_name=region)

    auth_result = require_tenant_auth(event, table, tenant_slug, region)
    if auth_result[0] is not True:
        _, err_resp = auth_result
        return _json_response(err_resp.get("statusCode", 401), json.loads(err_resp.get("body", "{}")))
    _, sub_or_username, role, is_cognito = auth_result

    if is_cognito:
        ok, err = require_tenant_admin_or_manager(table, sub_or_username, tenant_slug, event)
        if not ok:
            return _json_response(403, {"error": err or "Forbidden."})
    elif not role_is_admin_or_manager(role):
        return _json_response(403, {"error": "Admin or manager role required."})

    site_key = get_site_item(tenant_slug, site_id)
    site_resp = table.get_item(Key=site_key)
    site_item = site_resp.get("Item")
    if not site_item:
        return _json_response(404, {"error": "Site not found."})

    template_id = (site_item.get("template_id") or "").strip().lower()
    if not template_id:
        return _json_response(400, {"error": "Site has no template_id. Set a template before publishing."})

    # Resolve template: tenant first, then platform (Task 1.125)
    template_resp = table.get_item(Key=get_tenant_template_item(tenant_slug, template_id))
    template_item = template_resp.get("Item")
    if not template_item:
        template_resp = table.get_item(Key=get_template_item(template_id))
        template_item = template_resp.get("Item")
    if not template_item:
        return _json_response(404, {"error": f"Template not found: {template_id}"})

    tenant_resp = table.get_item(Key=get_tenant_item(tenant_slug))
    tenant_item = tenant_resp.get("Item") or {}
    resolved_features = _resolve_features(tenant_item)

    media_base = os.environ.get("CLOUDFRONT_MEDIA_URL", "/media/")

    try:
        result = _publish_site(
            table, s3_client, tenant_slug, site_id, site_item, template_item, media_base, resolved_features
        )
        return _json_response(200, {"publish": result})
    except BotoClientError as e:
        return _json_response(500, {"error": "Publish failed.", "detail": str(e)})
