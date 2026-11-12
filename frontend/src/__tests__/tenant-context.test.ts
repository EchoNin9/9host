import { describe, it, expect } from "vitest"
import { PLATFORM_SUBDOMAINS, extractTenantFromHost } from "@/contexts/tenant-context"

describe("extractTenantFromHost platform hosts (T-18)", () => {
  it.each(["app.echo9.net", "stage.echo9.net", "prod.echo9.net", "www.echo9.net", "echo9.net", "APP.echo9.ca"])(
    "%s has no tenant",
    (host) => {
      expect(extractTenantFromHost(host)).toBeNull()
    }
  )

  it("treats every reserved label as a platform host", () => {
    for (const label of PLATFORM_SUBDOMAINS) {
      expect(extractTenantFromHost(`${label}.echo9.net`, "echo9.net")).toBeNull()
    }
  })

  it("mirrors the backend reserved slug list", () => {
    expect([...PLATFORM_SUBDOMAINS].sort()).toEqual(
      ["admin", "api", "app", "preview", "prod", "proxy", "sites-origin", "stage", "tools", "www"]
    )
  })

  it("still resolves tenant subdomains", () => {
    expect(extractTenantFromHost("acme.echo9.net")).toBe("acme")
    expect(extractTenantFromHost("acme.echo9.ca")).toBe("acme")
  })
})
