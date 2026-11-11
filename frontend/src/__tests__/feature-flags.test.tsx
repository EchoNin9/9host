import { describe, it, expect, vi, afterEach } from "vitest"
import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import { isBillingEnabled } from "@/lib/feature-flags"
import { FeatureGate } from "@/components/feature-gate"
import { UpgradePrompt } from "@/components/upgrade-prompt"
import { TenantSettings } from "@/pages/tenant-settings"
import { TierContext } from "@/contexts/tier-context"

// Mock tenant hooks for TenantSettings rendering
vi.mock("@/hooks/use-tenant", () => ({
  useTenant: () => ({ tenantSlug: "test-tenant", tenantBasePath: "/test-tenant" }),
}))
vi.mock("@/context/tenant-scope", () => ({
  useTenantScope: () => ({ tenantSlug: "test-tenant", isSuperadminImpersonating: false, api: {} }),
}))
vi.mock("@/hooks/use-tenant-role", () => ({
  useTenantRole: () => ({ role: "admin", canEdit: true }),
}))
vi.mock("@/hooks/use-tenant-metadata", () => ({
  useTenantMetadata: () => ({
    tenant: { tenant_slug: "test-tenant", tier: "free", owner_sub: "owner123" },
    loading: false,
    refetch: vi.fn(),
  }),
}))
vi.mock("@/hooks/use-tenant-users", () => ({
  useTenantUsers: () => ({ users: [] }),
}))
vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({ userId: "owner123", isSiteUser: false }),
}))

describe("Billing Feature Flag (frontend)", () => {
  afterEach(() => {
    vi.unstubAllEnvs()
  })

  describe("isBillingEnabled helper and BILLING_ENABLED constant", () => {
    it("returns false when VITE_ENABLE_BILLING is unset or 'false'", async () => {
      vi.stubEnv("VITE_ENABLE_BILLING", "false")
      expect(isBillingEnabled()).toBe(false)

      vi.stubEnv("VITE_ENABLE_BILLING", "")
      expect(isBillingEnabled()).toBe(false)
    })

    it("returns true when VITE_ENABLE_BILLING is 'true'", async () => {
      vi.stubEnv("VITE_ENABLE_BILLING", "true")
      expect(isBillingEnabled()).toBe(true)
    })

    it("evaluates BILLING_ENABLED constant on module import", async () => {
      vi.resetModules()
      vi.stubEnv("VITE_ENABLE_BILLING", "true")
      const modTrue = await import("@/lib/feature-flags")
      expect(modTrue.BILLING_ENABLED).toBe(true)

      vi.resetModules()
      vi.stubEnv("VITE_ENABLE_BILLING", "false")
      const modFalse = await import("@/lib/feature-flags")
      expect(modFalse.BILLING_ENABLED).toBe(false)
    })
  })

  describe("UpgradePrompt component", () => {
    it("renders nothing when billing is disabled", () => {
      vi.stubEnv("VITE_ENABLE_BILLING", "false")
      const { container } = render(
        <MemoryRouter>
          <UpgradePrompt feature="custom_domains" />
        </MemoryRouter>
      )
      expect(container.firstChild).toBeNull()
    })

    it("renders upgrade card and CTA when billing is enabled", () => {
      vi.stubEnv("VITE_ENABLE_BILLING", "true")
      render(
        <MemoryRouter>
          <UpgradePrompt feature="custom_domains" />
        </MemoryRouter>
      )
      expect(screen.getByText("Custom domains")).toBeDefined()
      expect(screen.getByText("Upgrade plan")).toBeDefined()
    })
  })

  describe("FeatureGate component", () => {
    it("hides upgrade prompt when feature is locked and billing is disabled", () => {
      vi.stubEnv("VITE_ENABLE_BILLING", "false")
      const { container } = render(
        <MemoryRouter>
          <TierContext.Provider value={{ tier: "free" }}>
            <FeatureGate feature="custom_domains">
              <div>Protected Custom Domain Content</div>
            </FeatureGate>
          </TierContext.Provider>
        </MemoryRouter>
      )
      // Child is locked
      expect(screen.queryByText("Protected Custom Domain Content")).toBeNull()
      // Upgrade CTA is NOT rendered
      expect(screen.queryByText("Upgrade plan")).toBeNull()
      expect(screen.queryByText("Custom domains")).toBeNull()
      expect(container.textContent).toBe("")
    })

    it("shows upgrade prompt when feature is locked and billing is enabled", () => {
      vi.stubEnv("VITE_ENABLE_BILLING", "true")
      render(
        <MemoryRouter>
          <TierContext.Provider value={{ tier: "free" }}>
            <FeatureGate feature="custom_domains">
              <div>Protected Custom Domain Content</div>
            </FeatureGate>
          </TierContext.Provider>
        </MemoryRouter>
      )
      expect(screen.queryByText("Protected Custom Domain Content")).toBeNull()
      expect(screen.getByText("Upgrade plan")).toBeDefined()
    })

    it("renders child content when tier unlocks feature regardless of billing flag", () => {
      vi.stubEnv("VITE_ENABLE_BILLING", "false")
      render(
        <MemoryRouter>
          <TierContext.Provider value={{ tier: "pro" }}>
            <FeatureGate feature="custom_domains">
              <div>Protected Custom Domain Content</div>
            </FeatureGate>
          </TierContext.Provider>
        </MemoryRouter>
      )
      expect(screen.getByText("Protected Custom Domain Content")).toBeDefined()
    })
  })

  describe("TenantSettings billing section", () => {
    it("hides Billing card when billing is disabled", () => {
      vi.stubEnv("VITE_ENABLE_BILLING", "false")
      render(
        <MemoryRouter>
          <TenantSettings />
        </MemoryRouter>
      )
      expect(screen.queryByText("Billing")).toBeNull()
      expect(screen.queryByText("Manage your subscription and tier")).toBeNull()
      expect(screen.queryByText("Upgrade to Pro")).toBeNull()
      // Other settings are still visible
      expect(screen.getByText("Tenant settings")).toBeDefined()
    })

    it("shows Billing card and upgrade buttons when billing is enabled", () => {
      vi.stubEnv("VITE_ENABLE_BILLING", "true")
      render(
        <MemoryRouter>
          <TenantSettings />
        </MemoryRouter>
      )
      expect(screen.getByText("Billing")).toBeDefined()
      expect(screen.getByText("Manage your subscription and tier")).toBeDefined()
      expect(screen.getByText("Upgrade to Pro")).toBeDefined()
    })
  })
})
