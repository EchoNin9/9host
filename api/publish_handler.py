"""
Site publish API (Task 1.96, 1.109).

POST /api/tenant/sites/{id}/publish — atomic versioned publish:
  render HTML from template + content → upload to published/v{N}/ →
  copy to current/ → manifest.json → current.json → update Site.

Task 1.109: Template-aware rendering — components, sections, /blog/, /posts/{slug}/,
/events/, branding injection.
Task 1.111: Wire media URLs as /media/{tenant}/{site}/{filename} in rendered HTML.
"""

import hashlib
import json
import os
import re
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError as BotoClientError

from auth_helpers import require_tenant_admin_or_manager, require_tenant_auth, role_is_admin_or_manager
from dynamodb_helpers import get_site_item, get_template_item, pk_tenant
from middleware import with_tenant

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


def _escape_html(s: str) -> str:
    if not s:
        return ""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _media_url(s3_key: str, media_base: str) -> str:
    """Build media URL for published HTML (Task 1.111). Format: /media/{tenant}/{site}/{filename}."""
    if not s3_key:
        return ""
    base = (media_base or "/media").rstrip("/")
    return f"{base}/{s3_key}"


def _rewrite_body_media_urls(body: str, tenant_slug: str, site_id: str, media_base: str) -> str:
    """Rewrite S3/presigned URLs in body to /media/{tenant}/{site}/{filename} (Task 1.111)."""
    if not body or not isinstance(body, str):
        return body or ""
    # Match S3 URLs containing {tenant}/{site_id}/... (e.g. presigned or direct)
    pattern = re.compile(
        r"https?://[^\s\"'<>]*?/" + re.escape(f"{tenant_slug}/{site_id}/") + r"([^\s\"'<>?#]+)",
        re.IGNORECASE,
    )
    base = (media_base or "/media").rstrip("/")

    def repl(m: re.Match) -> str:
        return f"{base}/{tenant_slug}/{site_id}/{m.group(1)}"

    return pattern.sub(repl, body)


def _branding_styles(branding: dict) -> str:
    """Generate CSS from site.branding (primary_color, font_family)."""
    if not branding or not isinstance(branding, dict):
        return ""
    parts = []
    if branding.get("primary_color"):
        parts.append(f"  --brand-primary: {_escape_html(branding['primary_color'])};")
    if branding.get("font_family"):
        parts.append(f"  font-family: {_escape_html(branding['font_family'])};")
    if not parts:
        return ""
    return "<style>\n:root {\n" + "\n".join(parts) + "\n}\n</style>\n  "


def _html_head(title: str, site_name: str, branding: dict) -> str:
    """Shared head with branding injection."""
    styles = _branding_styles(branding)
    return f"""  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_escape_html(title or site_name)} — {_escape_html(site_name)}</title>
{styles}"""


def _html_header(site_name: str, branding: dict, media_base: str, nav_links: str) -> str:
    """Shared header with logo and nav."""
    logo_html = ""
    if branding and isinstance(branding, dict) and branding.get("logo_s3_key"):
        logo_url = _media_url(branding["logo_s3_key"], media_base)
        logo_html = f'<img src="{_escape_html(logo_url)}" alt="" class="site-logo"> '
    return f"""  <header>
    {logo_html}<h1>{_escape_html(site_name)}</h1>
    <nav><ul>{nav_links}</ul></nav>
  </header>"""


def _nav_links(pages: list, has_posts: bool, has_events: bool, has_media: bool = False) -> str:
    """Build nav links from pages + blog + events + gallery (Task 1.111)."""
    links = []
    for p in pages:
        path = (p.get("path") or "").strip()
        if path:
            links.append(f'<li><a href="/{path}/">{_escape_html(p.get("title") or path)}</a></li>')
    if has_posts:
        links.append('<li><a href="/blog/">Blog</a></li>')
    if has_events:
        links.append('<li><a href="/events/">Events</a></li>')
    if has_media:
        links.append('<li><a href="/gallery/">Gallery</a></li>')
    return "\n      ".join(links) if links else ""


def _render_page_html(
    path: str,
    title: str,
    body: str,
    site_name: str,
    branding: dict,
    media_base: str,
    nav: str,
    tenant_slug: str = "",
    site_id: str = "",
) -> str:
    """Render a single page as HTML (Task 1.109, 1.111: branding, media URL rewrite)."""
    body_rewritten = (
        _rewrite_body_media_urls(body, tenant_slug, site_id, media_base) if tenant_slug and site_id else (body or "")
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{_html_head(title or path, site_name, branding)}
</head>
<body>
{_html_header(site_name, branding, media_base, nav)}
  <main>
    <h2>{_escape_html(title or path)}</h2>
    <div class="content">{body_rewritten}</div>
  </main>
</body>
</html>"""


def _render_index_html(
    site_name: str, pages: list, posts: list, events: list, branding: dict, media_base: str, has_media: bool = False
) -> str:
    """Render index.html with links (Task 1.109, 1.111: branding, nav, gallery)."""
    nav = _nav_links(pages, bool(posts), bool(events), has_media)
    links = "".join(
        f'    <li><a href="/{p["path"]}/">{_escape_html(p["title"] or p["path"])}</a></li>\n'
        for p in pages
    )
    if posts:
        links += '    <li><a href="/blog/">Blog</a></li>\n'
    if events:
        links += '    <li><a href="/events/">Events</a></li>\n'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{_html_head(site_name, site_name, branding)}
</head>
<body>
{_html_header(site_name, branding, media_base, nav)}
  <main>
    <h2>Welcome</h2>
    <nav><ul>
{links}
    </ul></nav>
  </main>
</body>
</html>"""


def _render_blog_index(
    site_name: str, posts: list, branding: dict, media_base: str, nav: str
) -> str:
    """Render /blog/ index (Task 1.109)."""
    items = "".join(
        f'    <li><a href="/posts/{_escape_html(p["slug"])}/">{_escape_html(p["title"] or p["slug"])}</a></li>\n'
        for p in posts
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{_html_head("Blog", site_name, branding)}
</head>
<body>
{_html_header(site_name, branding, media_base, nav)}
  <main>
    <h2>Blog</h2>
    <ul class="posts-list">
{items or "    <li>No posts yet.</li>\n"}
    </ul>
  </main>
</body>
</html>"""


def _render_post_detail(
    post: dict,
    site_name: str,
    branding: dict,
    media_base: str,
    nav: str,
    tenant_slug: str = "",
    site_id: str = "",
) -> str:
    """Render /posts/{slug}/ detail (Task 1.109, 1.111: media URL rewrite)."""
    body = post.get("body", "")
    body_rewritten = (
        _rewrite_body_media_urls(body, tenant_slug, site_id, media_base) if tenant_slug and site_id else body
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{_html_head(post.get("title", ""), site_name, branding)}
</head>
<body>
{_html_header(site_name, branding, media_base, nav)}
  <main>
    <h2>{_escape_html(post.get("title", ""))}</h2>
    <div class="content">{body_rewritten}</div>
  </main>
</body>
</html>"""


def _render_events_page(
    site_name: str, events: list, branding: dict, media_base: str, nav: str
) -> str:
    """Render /events/ page (Task 1.109)."""
    items = "".join(
        f'    <li><strong>{_escape_html(e.get("title", ""))}</strong> — {_escape_html(e.get("event_date", ""))}'
        + (f' @ {_escape_html(e.get("venue", ""))}' if e.get("venue") else "")
        + "</li>\n"
        for e in events
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{_html_head("Events", site_name, branding)}
</head>
<body>
{_html_header(site_name, branding, media_base, nav)}
  <main>
    <h2>Events</h2>
    <ul class="events-list">
{items or "    <li>No events yet.</li>\n"}
    </ul>
  </main>
</body>
</html>"""


def _render_gallery_page(
    site_name: str, media: list, branding: dict, media_base: str, nav: str
) -> str:
    """Render /gallery/ page with media using /media/{tenant}/{site}/{filename} URLs (Task 1.111)."""
    items = "".join(
        f'    <figure><img src="{_escape_html(_media_url(m.get("s3_key", ""), media_base))}" alt="{_escape_html(m.get("caption", ""))}"><figcaption>{_escape_html(m.get("caption", ""))}</figcaption></figure>\n'
        for m in media
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{_html_head("Gallery", site_name, branding)}
</head>
<body>
{_html_header(site_name, branding, media_base, nav)}
  <main>
    <h2>Gallery</h2>
    <div class="media-gallery">
{items or "    <p>No media yet.</p>\n"}
    </div>
  </main>
</body>
</html>"""


def _collect_published_content(table, tenant_slug: str, site_id: str) -> dict:
    """Fetch all PUBLISHED content for the site."""
    pages = []
    posts = []
    events = []
    media = []

    for entity, sk_prefix in [
        ("PAGE", "PAGE#"),
        ("POST", "POST#"),
        ("EVENT", "EVENT#"),
        ("MEDIA", "MEDIA#"),
    ]:
        params = {
            "KeyConditionExpression": "pk = :pk AND begins_with(sk, :sk)",
            "ExpressionAttributeValues": {
                ":pk": pk_tenant(tenant_slug),
                ":sk": f"SITE#{site_id}#{entity}#",
            },
        }
        resp = table.query(**params)
        for item in resp.get("Items", []):
            if (item.get("status") or "").upper() != "PUBLISHED":
                continue
            if entity == "PAGE":
                path = item.get("path", "")
                pages.append(
                    {
                        "path": path,
                        "title": item.get("title", ""),
                        "body": item.get("body", ""),
                    }
                )
            elif entity == "POST":
                slug = item.get("slug", "")
                posts.append(
                    {
                        "slug": slug,
                        "title": item.get("title", ""),
                        "body": item.get("body", ""),
                    }
                )
            elif entity == "EVENT":
                events.append(
                    {
                        "title": item.get("title", ""),
                        "event_date": item.get("event_date", ""),
                        "venue": item.get("venue", ""),
                    }
                )
            elif entity == "MEDIA":
                media.append(
                    {
                        "s3_key": item.get("s3_key", ""),
                        "caption": item.get("caption", ""),
                    }
                )

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
        s3_client.put_object(
            Bucket=bucket,
            Key=key_v,
            Body=body,
            ContentType="text/html; charset=utf-8" if path.endswith(".html") else "application/octet-stream",
            CacheControl=HTML_CACHE_CONTROL if path.endswith(".html") else ASSET_CACHE_CONTROL,
        )

        # Copy to current/
        key_current = f"{current_prefix}{path}"
        s3_client.copy_object(
            Bucket=bucket,
            CopySource={"Bucket": bucket, "Key": key_v},
            Key=key_current,
            CacheControl=HTML_CACHE_CONTROL if path.endswith(".html") else ASSET_CACHE_CONTROL,
        )

        # If default site, copy to default/
        if is_default:
            key_default = f"{default_prefix}{path}"
            s3_client.copy_object(
                Bucket=bucket,
                CopySource={"Bucket": bucket, "Key": key_v},
                Key=key_default,
                CacheControl=HTML_CACHE_CONTROL if path.endswith(".html") else ASSET_CACHE_CONTROL,
            )

    return manifest_entries


def _publish_site(
    table,
    s3_client,
    tenant_slug: str,
    site_id: str,
    site_item: dict,
    template_item: dict,
    media_base: str,
) -> dict:
    """Perform the publish flow (Task 1.109, 1.111: template-aware, blog, events, branding, media URLs)."""
    site_name = site_item.get("name", "Site")
    branding = site_item.get("branding") if isinstance(site_item.get("branding"), dict) else {}
    content = _collect_published_content(table, tenant_slug, site_id)
    pages = content["pages"]
    posts = content["posts"]
    events = content["events"]
    media = content["media"]

    nav = _nav_links(pages, bool(posts), bool(events), bool(media))

    # Build files to publish
    files = {}

    # index.html
    files["index.html"] = _render_index_html(
        site_name, pages, posts, events, branding, media_base, bool(media)
    )

    # Per-page HTML (template components: pages)
    for p in pages:
        path = p.get("path", "").strip()
        if not path:
            continue
        html = _render_page_html(
            p["path"], p["title"], p["body"], site_name, branding, media_base, nav,
            tenant_slug, site_id,
        )
        files[f"{path}/index.html"] = html

    # Task 1.109: /blog/ (posts index)
    if posts:
        files["blog/index.html"] = _render_blog_index(site_name, posts, branding, media_base, nav)

    # Task 1.109: /posts/{slug}/ (post detail)
    for post in posts:
        slug = (post.get("slug") or "").strip()
        if slug:
            files[f"posts/{slug}/index.html"] = _render_post_detail(
                post, site_name, branding, media_base, nav, tenant_slug, site_id
            )

    # Task 1.109: /events/
    if events:
        files["events/index.html"] = _render_events_page(
            site_name, events, branding, media_base, nav
        )

    # Task 1.111: /gallery/ (media with /media/{tenant}/{site}/{filename} URLs)
    if media:
        files["gallery/index.html"] = _render_gallery_page(
            site_name, media, branding, media_base, nav
        )

    if not files:
        files["index.html"] = _render_index_html(
            site_name, [], [], [], branding, media_base, bool(media)
        )

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

    template_resp = table.get_item(Key=get_template_item(template_id))
    template_item = template_resp.get("Item")
    if not template_item:
        return _json_response(404, {"error": f"Template not found: {template_id}"})

    media_base = os.environ.get("CLOUDFRONT_MEDIA_URL", "/media/")

    try:
        result = _publish_site(
            table, s3_client, tenant_slug, site_id, site_item, template_item, media_base
        )
        return _json_response(200, {"publish": result})
    except BotoClientError as e:
        return _json_response(500, {"error": "Publish failed.", "detail": str(e)})
