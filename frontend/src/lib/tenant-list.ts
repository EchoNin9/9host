/**
 * Tenant list for switcher. Demo tenants until API returns user's tenants (GSI byUser).
 */

const DEMO_TENANTS = ["acme", "demo"] as const;

export function getDemoTenants(): string[] {
  return [...DEMO_TENANTS];
}
