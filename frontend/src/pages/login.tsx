"use client"

import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { signIn, fetchAuthSession } from "aws-amplify/auth"
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
      const { nextStep } = await signIn({ username: email, password })
      if (nextStep?.signInStep === "CONFIRM_SIGN_UP") {
        navigate("/auth/confirm", { state: { email } })
        return
      }

      const destination = await resolvePostLoginDestination()
      navigate(destination, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed")
    } finally {
      setLoading(false)
    }
  }

  async function resolvePostLoginDestination(): Promise<string> {
    const delay = (ms: number) => new Promise((r) => setTimeout(r, ms))

    for (let attempt = 0; attempt < 2; attempt++) {
      if (attempt > 0) await delay(150)
      else await delay(100)

      try {
        const session = await fetchAuthSession()
        const token = session.tokens?.accessToken?.toString() ?? null
        if (!token) continue

        const { isSuperadmin } = await fetchAllTenants(token)
        if (isSuperadmin) return "/admin"

        const tenants = await fetchTenants(token)
        if (tenants.length === 1) return `/${tenants[0].slug}`
        return "/"
      } catch {
        // Retry on next attempt
      }
    }
    return "/"
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
