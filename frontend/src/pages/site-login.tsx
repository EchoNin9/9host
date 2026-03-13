"use client"

import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { siteLogin, SITE_TOKEN_KEY, SITE_USER_DISPLAY_KEY } from "@/lib/api"

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
      if (!result) {
        setError("Invalid username, password, or site")
        setLoading(false)
        return
      }
      localStorage.setItem(SITE_TOKEN_KEY, result.token)
      const display = (result.display_name || result.username || "").trim()
      if (display) localStorage.setItem(SITE_USER_DISPLAY_KEY, display)
      navigate(`/${result.tenant_slug}`, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-8">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Sign in to your site</CardTitle>
          <CardDescription>
            Use your site username and password. Enter your site slug (e.g. acme-corp).
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {error && (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            )}
            <div className="space-y-2">
              <label htmlFor="site-username" className="text-sm font-medium">
                Username
              </label>
              <Input
                id="site-username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="jane"
                required
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="site-password" className="text-sm font-medium">
                Password
              </label>
              <Input
                id="site-password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="site-slug" className="text-sm font-medium">
                Site
              </label>
              <Input
                id="site-slug"
                type="text"
                autoComplete="organization"
                value={site}
                onChange={(e) => setSite(e.target.value)}
                placeholder="acme-corp"
                required
              />
              <p className="text-xs text-muted-foreground">
                Your tenant slug (e.g. acme-corp)
              </p>
            </div>
          </CardContent>
          <CardFooter className="flex flex-col gap-2">
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Signing in…" : "Sign in"}
            </Button>
            <p className="text-center text-sm text-muted-foreground">
              <Link to="/login" className="underline hover:text-foreground">
                Sign in with email (Cognito)
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>
    </div>
  )
}
