import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { TenantPage, TenantPageTitle } from "@/components/tenant-page"
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
    expect(h.parentElement?.classList.contains("p-6")).toBe(true)
  })

  it("embedded in the console: unpadded with an h2", () => {
    render(
      <TenantScopeContext.Provider value={scope(true)}>
        <Page />
      </TenantScopeContext.Provider>
    )
    const h = screen.getByRole("heading", { name: "Sites" })
    expect(h.tagName).toBe("H2")
    expect(h.parentElement?.classList.contains("p-6")).toBe(false)
  })

  it("works without a TenantScopeProvider", () => {
    render(<Page />)
    expect(screen.getByRole("heading", { name: "Sites" }).tagName).toBe("H1")
  })
})
