import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { TenantPage, TenantPageHeader, TenantPageTitle } from "@/components/tenant-page"
import { TenantScopeContext, type TenantScopeValue } from "@/context/tenant-scope-context"

const scope = (embedded: boolean) =>
  ({ tenantSlug: "acme", isSuperadminImpersonating: true, basePath: "/admin/tenants/acme", embedded, api: {} }) as unknown as TenantScopeValue

function Page() {
  return (
    <TenantPage>
      <TenantPageTitle>Sites</TenantPageTitle>
    </TenantPage>
  )
}

describe("TenantPage (T-18: no double padding / duplicate h1 in the Superadmin Console)", () => {
  it("standalone: padded page with an h1", () => {
    render(
      <TenantScopeContext.Provider value={scope(false)}>
        <Page />
      </TenantScopeContext.Provider>
    )
    const h = screen.getByRole("heading", { name: "Sites" })
    expect(h.tagName).toBe("H1")
    const page = h.closest("[data-slot=tenant-page]")
    expect(page?.className).toMatch(/\bpx-4\b/)
    expect(page?.hasAttribute("data-embedded")).toBe(false)
  })

  it("embedded in the console: unpadded with an h2", () => {
    render(
      <TenantScopeContext.Provider value={scope(true)}>
        <Page />
      </TenantScopeContext.Provider>
    )
    const h = screen.getByRole("heading", { name: "Sites" })
    expect(h.tagName).toBe("H2")
    const page = h.closest("[data-slot=tenant-page]")
    expect(page?.className).not.toMatch(/\b(p|px|py)-\d/)
    expect(page?.getAttribute("data-embedded")).toBe("true")
  })

  it("works without a TenantScopeProvider", () => {
    render(<Page />)
    expect(screen.getByRole("heading", { name: "Sites" }).tagName).toBe("H1")
  })

  it("TenantPageHeader follows the same heading level", () => {
    const { rerender } = render(
      <MemoryRouter>
        <TenantScopeContext.Provider value={scope(true)}>
          <TenantPageHeader title="Domains" />
        </TenantScopeContext.Provider>
      </MemoryRouter>
    )
    expect(screen.getByRole("heading", { name: "Domains" }).tagName).toBe("H2")
    rerender(
      <MemoryRouter>
        <TenantScopeContext.Provider value={scope(false)}>
          <TenantPageHeader title="Domains" />
        </TenantScopeContext.Provider>
      </MemoryRouter>
    )
    expect(screen.getByRole("heading", { name: "Domains" }).tagName).toBe("H1")
  })
})
