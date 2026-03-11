# Site Templates

> **Task 1.30–1.33.** Platform-level site templates. Same backend components, different configs. Tier-gated.

---

## Template Slugs

| Slug | Name | Tier Required | Description |
|------|------|---------------|-------------|
| musician-band | Musician / Band | FREE | Band/artist site: bio, discography, tour dates, media |
| personal-tech | Personal Tech | FREE | Developer/tech portfolio: projects, blog, links |
| personal-resume | Personal Resume | FREE | Resume/CV: experience, skills, contact |
| professional-services | Professional Services | PRO | Consultant/agency: services, case studies, contact |
| business-generic | Business Generic | PRO | Generic business: about, services, team, contact |

---

## Components Structure

Templates use the same backend components. The `components` map defines which pages/sections to include and their default config.

```json
{
  "pages": ["home", "about", "contact"],
  "sections": {
    "home": ["hero", "features", "cta"],
    "about": ["bio", "team"]
  },
  "defaults": {
    "theme": "default",
    "layout": "single-column"
  }
}
```

**Backend components:** Shared across all templates. Template defines composition, not implementation.

---

## API

- **GET /api/templates** — List templates available to tenant (filtered by tenant.tier >= template.tier_required). Requires tenant_slug, Cognito auth.
- **GET /api/admin/templates** — List all templates (superadmin).
- **POST /api/admin/templates** — Create template (superadmin).
- **PUT /api/admin/templates/{slug}** — Update template (superadmin).
- **DELETE /api/admin/templates/{slug}** — Remove template (superadmin).

---

## Site Creation

POST /api/tenant/sites accepts optional `template_id`. If provided:

1. Validate template exists.
2. Validate tenant.tier >= template.tier_required.
3. Store template_id on site.
4. Site inherits template's components structure (frontend applies).
