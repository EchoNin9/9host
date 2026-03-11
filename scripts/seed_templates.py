#!/usr/bin/env python3
"""
Seed platform site templates (Task 1.33).

Populates DynamoDB with musician-band, personal-tech, personal-resume,
professional-services, business-generic. Idempotent — safe to run multiple times.

Usage:
  python scripts/seed_templates.py --table 9host-main
  python scripts/seed_templates.py --table 9host-main --dry-run
"""

import argparse
import os
import sys
from datetime import datetime, timezone

import boto3

# From dynamodb_helpers
PLATFORM_TENANT = "_platform"


def pk_tenant(slug: str) -> str:
    return f"TENANT#{slug}"


def sk_template(slug: str) -> str:
    return f"TEMPLATE#{slug}"


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


def seed(table_name: str, dry_run: bool) -> int:
    """Seed templates. Returns count seeded."""
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    now = datetime.now(timezone.utc).isoformat()
    seeded = 0

    for t in TEMPLATES:
        slug = t["slug"]
        item = {
            "pk": pk_tenant(PLATFORM_TENANT),
            "sk": sk_template(slug),
            "slug": slug,
            "name": t["name"],
            "description": t["description"],
            "tier_required": t["tier_required"],
            "components": t["components"],
            "created_at": now,
            "updated_at": now,
        }

        if dry_run:
            print(f"  Would seed: {slug} ({t['name']})")
        else:
            table.put_item(Item=item)
            print(f"  Seeded: {slug} ({t['name']})")

        seeded += 1

    return seeded


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed platform site templates")
    parser.add_argument("--table", default=os.environ.get("DYNAMODB_TABLE", "9host-main"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"Seeding {len(TEMPLATES)} templates to table {args.table}...")
    seed(args.table, args.dry_run)
    print(f"Done. {len(TEMPLATES)} template(s) {'would be ' if args.dry_run else ''}seeded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
