"use client"

import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { signIn, fetchAuthSession } from "aws-amplify/auth"
import { Hub } from "aws-amplify/utils"
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
import { fetchAllTenants, fetchTenants } from "@/lib/api"

export function Login() {
  const navigate = useNavigate()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const signedInPromise = new Promise<void>((resolve) => {
        const cancel = Hub.listen("auth", ({ payload }) => {
          if (payload.event === "signedIn") {
            cancel()
            resolve()
          }
        })
        setTimeout(() => {
          cancel()
          resolve()
        }, 3000)
      })

      const { nextStep } = await signIn({ username: email, password })
      if (nextStep?.signInStep === "CONFIRM_SIGN_UP") {
        navigate("/auth/confirm", { state: { email } })
        return
      }

      await signedInPromise

      const destination = await resolvePostLoginDestination()
      navigate(destination, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed")
    } finally {
      setLoading(false)
    }
  }

  async function resolvePostLoginDestination(): Promise<string> {
    const DBG = (msg: string, data?: unknown) =>
      console.log("[9host post-login]", msg, data ?? "")

    try {
      const session = await fetchAuthSession()
      const token = session.tokens?.accessToken?.toString() ?? null
      DBG("fetchAuthSession", {
        hasTokens: !!session.tokens,
        hasAccessToken: !!session.tokens?.accessToken,
        tokenLength: token?.length ?? 0,
      })
      if (!token) {
        DBG("no token after Hub signedIn")
        return "/"
      }

      const { isSuperadmin, tenants: adminTenants } =
        await fetchAllTenants(token)
      DBG("fetchAllTenants", { isSuperadmin, tenantCount: adminTenants?.length })

      if (isSuperadmin) {
        DBG("redirecting to /admin")
        return "/admin"
      }

      const tenants = await fetchTenants(token)
      DBG("fetchTenants", {
        count: tenants.length,
        slugs: tenants.map((t) => t.slug),
      })
      if (tenants.length === 1) {
        DBG("redirecting to tenant", tenants[0].slug)
        return `/${tenants[0].slug}`
      }
      DBG("fallback to /")
      return "/"
    } catch (err) {
      DBG("error", err)
      return "/"
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-8">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Sign in</CardTitle>
          <CardDescription>Sign in to 9host with your email</CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {error && (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            )}
            <div className="space-y-2">
              <label htmlFor="email" className="text-sm font-medium">
                Email
              </label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium">
                Password
              </label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
          </CardContent>
          <CardFooter className="flex flex-col gap-2">
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Signing in…" : "Sign in"}
            </Button>
            <p className="text-center text-sm text-muted-foreground">
              Don&apos;t have an account?{" "}
              <Link to="/signup" className="underline hover:text-foreground">
                Sign up
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>
    </div>
  )
}
