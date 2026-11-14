#!/usr/bin/env python3
"""
Seed / migrate platform site templates (Task 1.33; T-32a versioning, ADR-0003 §5).

For each template below, in the TENANT#_platform partition only:
  - head TEMPLATE#{slug} missing  -> create it (metadata + components + base_renderer,
                                     latest_version=1, published_version=1)
  - head present                  -> SET only the attributes it lacks (base_renderer,
                                     latest_version, published_version); superadmin edits to
                                     name/description/tier are never overwritten
  - version TEMPLATE#{slug}#V#0001 missing -> write it (conditional put; never overwritten).
    Presets come from components.pages: one placeholder RichText block per section
    ("home" -> "_home"; compiler-generated paths like "blog" are skipped).
Idempotent: a second run performs no writes.

Usage:
  python scripts/seed_templates.py --table 9host-main
  python scripts/seed_templates.py --table 9host-main --dry-run
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from datetime import datetime, timezone  # noqa: E402

from template_schema import GENERATED_PATHS, presets_to_store, validate_version  # noqa: E402

TEMPLATES = [
    {
        "slug": "musician-band",
        "name": "Musician / Band",
        "description": "Band/artist site: bio, discography, tour dates, media",
        "tier_required": "FREE",
        "components": {
            "pages": ["home", "about", "music", "tour", "contact"],
            "sections": {
                "home": ["hero", "featured", "cta"],
                "about": ["bio", "band"],
                "music": ["discography", "player"],
                "tour": ["dates", "venues"],
                "contact": ["form", "links"],
            },
            "defaults": {"theme": "default", "layout": "single-column"},
        },
    },
    {
        "slug": "personal-tech",
        "name": "Personal Tech",
        "description": "Developer/tech portfolio: projects, blog, links",
        "tier_required": "FREE",
        "components": {
            "pages": ["home", "projects", "blog", "about", "contact"],
            "sections": {
                "home": ["hero", "projects-preview", "cta"],
                "projects": ["grid", "details"],
                "blog": ["posts", "sidebar"],
                "about": ["bio", "skills"],
                "contact": ["form", "links"],
            },
            "defaults": {"theme": "default", "layout": "single-column"},
        },
    },
    {
        "slug": "personal-resume",
        "name": "Personal Resume",
        "description": "Resume/CV: experience, skills, contact",
        "tier_required": "FREE",
        "components": {
            "pages": ["home", "experience", "skills", "contact"],
            "sections": {
                "home": ["hero", "summary"],
                "experience": ["timeline", "highlights"],
                "skills": ["categories", "tools"],
                "contact": ["form", "links"],
            },
            "defaults": {"theme": "default", "layout": "single-column"},
        },
    },
    {
        "slug": "professional-services",
        "name": "Professional Services",
        "description": "Consultant/agency: services, case studies, contact",
        "tier_required": "PRO",
        "components": {
            "pages": ["home", "services", "case-studies", "about", "contact"],
            "sections": {
                "home": ["hero", "services-preview", "cta"],
                "services": ["list", "details"],
                "case-studies": ["grid", "testimonials"],
                "about": ["bio", "team"],
                "contact": ["form", "consultation"],
            },
            "defaults": {"theme": "default", "layout": "single-column"},
        },
    },
    {
        "slug": "business-generic",
        "name": "Business Generic",
        "description": "Generic business: about, services, team, contact",
        "tier_required": "PRO",
        "components": {
            "pages": ["home", "about", "services", "team", "contact"],
            "sections": {
                "home": ["hero", "features", "cta"],
                "about": ["mission", "values"],
                "services": ["list", "pricing"],
                "team": ["grid", "bios"],
                "contact": ["form", "map"],
            },
            "defaults": {"theme": "default", "layout": "single-column"},
        },
    },
]


def v1_presets(components: dict) -> dict:
    """components.pages/sections -> {path: block doc}, one placeholder RichText per section."""
    presets = {}
    for page in components.get("pages") or []:
        path = "_home" if page == "home" else page
        if path in GENERATED_PATHS:
            continue
        title = page.replace("-", " ").title()
        sections = (components.get("sections") or {}).get(page) or ["content"]
        presets[path] = {
            "schema": 1,
            "root": {"props": {"title": title}},
            "content": [
                {"type": "RichText", "props": {
                    "html": f"<h2>{s.replace('-', ' ').title()}</h2><p>Placeholder text for this section.</p>"}}
                for s in sections
            ],
        }
    return presets


def v1_version(t: dict, now: str) -> dict:
    version = validate_version({"page_presets": v1_presets(t["components"])})
    version["page_presets"] = presets_to_store(version["page_presets"])
    version["created_at"] = now
    return version


def seed(store, dry_run: bool = False, now: str | None = None) -> dict:
    """Migrate/seed every template through TenantStore. Returns write counts (planned on dry run)."""
    now = now or datetime.now(timezone.utc).isoformat()
    counts = {"heads_created": 0, "heads_updated": 0, "versions_created": 0}
    tag = "[dry-run] " if dry_run else ""
    for t in TEMPLATES:
        slug = t["slug"]
        head = store.get_template(slug)
        if head is None:
            print(f"  {tag}create head {slug} ({t['name']})")
            counts["heads_created"] += 1
            if not dry_run:
                store.put_template_head(slug, {
                    "name": t["name"], "description": t["description"], "tier_required": t["tier_required"],
                    "components": t["components"], "base_renderer": slug, "latest_version": 1,
                    "published_version": 1, "deprecated": False, "created_at": now, "updated_at": now,
                }, create_only=True)
        else:
            missing = {}
            if not head.get("base_renderer"):
                missing["base_renderer"] = slug
            if not head.get("latest_version"):
                missing["latest_version"] = 1
            if head.get("published_version") is None:
                missing["published_version"] = 1
            if missing:
                print(f"  {tag}set {sorted(missing)} on head {slug}")
                counts["heads_updated"] += 1
                if not dry_run:
                    store.update_template_head(slug, missing)
        if store.get_template_version(slug, 1) is None:
            print(f"  {tag}write {slug} V0001")
            counts["versions_created"] += 1
            if not dry_run:
                store.put_template_version(slug, v1_version(t, now), n=1)
    return counts


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Seed / migrate platform site templates")
    parser.add_argument("--table", default=os.environ.get("DYNAMODB_TABLE", "9host-main"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    import boto3

    from tenant_store import DynamoDBTenantStore

    print(f"Seeding {len(TEMPLATES)} templates in table {args.table}{' (dry run)' if args.dry_run else ''}...")
    counts = seed(DynamoDBTenantStore(boto3.resource("dynamodb").Table(args.table)), args.dry_run)
    print(f"Done. {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
