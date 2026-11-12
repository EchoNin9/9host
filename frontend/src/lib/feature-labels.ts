import type { FeatureKey } from "@/lib/feature-flags"

/** User-facing name + one-line description per gated feature. */
export const FEATURE_LABELS: Record<FeatureKey, { title: string; description: string }> = {
  custom_domains: {
    title: "Custom domains",
    description: "Add custom domains to your sites. Requires Pro or Business tier.",
  },
  advanced_analytics: {
    title: "Advanced Analytics",
    description: "View page views, visitors, and top pages. Requires Pro or Business tier.",
  },
  updates_blog: {
    title: "Updates / Blog",
    description: "Blog posts and news updates. Available on all tiers.",
  },
  events_shows: {
    title: "Events & Shows",
    description: "Events, tour dates, and shows. Available on all tiers.",
  },
  media_gallery: {
    title: "Media Gallery",
    description: "Image gallery and media library. Requires Pro or Business tier.",
  },
  branding: {
    title: "Branding",
    description: "Logo, colors, fonts, and favicon. Available on all tiers.",
  },
}
