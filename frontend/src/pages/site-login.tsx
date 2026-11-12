"use client"

import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { AuthLayout } from "@/components/auth-layout"
import { FormField, Notice } from "@/components/page"
import { siteLogin, setSiteSession } from "@/lib/api"

export function SiteLogin() {
  const navigate = useNavigate()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [site, setSite] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const result = await siteLogin({
        username: username.trim(),
        password,
        site: site.trim().toLowerCase(),
      })
      if (result.ok) {
        const { data } = result
        setSiteSession(data.token, (data.display_name || data.username || "").trim() || null)
        navigate(`/${data.tenant_slug}`, { replace: true })
        return
      }
      setError(result.error)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout
      title="Site sign-in"
      description="For team members with a username created by their tenant admin."
      footer={
        <p>
          Have an Echo9 account?{" "}
          <Link to="/login" className="font-medium text-foreground underline underline-offset-4">
            Sign in with email
          </Link>
        </p>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <Notice tone="danger">{error}</Notice>}
        <FormField label="Tenant" htmlFor="site-slug" hint="The tenant slug, e.g. acme-corp from acme-corp.echo9.net.">
          <Input
            id="site-slug"
            type="text"
            autoComplete="organization"
            autoCapitalize="none"
            spellCheck={false}
            className="font-mono"
            value={site}
            onChange={(e) => setSite(e.target.value)}
            placeholder="acme-corp"
            required
            autoFocus
          />
        </FormField>
        <FormField label="Username" htmlFor="site-username">
          <Input
            id="site-username"
            type="text"
            autoComplete="username"
            autoCapitalize="none"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="jane"
            required
          />
        </FormField>
        <FormField label="Password" htmlFor="site-password">
          <Input
            id="site-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </FormField>
        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </AuthLayout>
  )
}
