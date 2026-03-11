"use client"

import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { signIn, confirmSignIn, fetchAuthSession } from "aws-amplify/auth"
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
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [needsNewPassword, setNeedsNewPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      if (needsNewPassword) {
        if (newPassword !== confirmPassword) {
          setError("Passwords do not match")
          setLoading(false)
          return
        }
        if (newPassword.length < 8) {
          setError("Password must be at least 8 characters")
          setLoading(false)
          return
        }
        await confirmSignIn({ challengeResponse: newPassword })
        const destination = await resolvePostLoginDestination()
        navigate(destination, { replace: true })
        return
      }

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
      if (nextStep?.signInStep === "CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED") {
        setNeedsNewPassword(true)
        setLoading(false)
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
    try {
      const session = await fetchAuthSession()
      const token = session.tokens?.accessToken?.toString() ?? null
      if (!token) return "/"

      const { isSuperadmin } = await fetchAllTenants(token)
      if (isSuperadmin) return "/admin"

      const tenants = await fetchTenants(token)
      if (tenants.length === 1) return `/${tenants[0].slug}`
      return "/"
    } catch {
      return "/"
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-8">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>
            {needsNewPassword ? "Set new password" : "Sign in"}
          </CardTitle>
          <CardDescription>
            {needsNewPassword
              ? "Your account requires a new password. Choose a secure password."
              : "Sign in to 9host with your email"}
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {error && (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            )}
            {!needsNewPassword && (
              <>
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
              </>
            )}
            {needsNewPassword && (
              <>
                <div className="space-y-2">
                  <label htmlFor="new-password" className="text-sm font-medium">
                    New password
                  </label>
                  <Input
                    id="new-password"
                    type="password"
                    autoComplete="new-password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                    minLength={8}
                  />
                </div>
                <div className="space-y-2">
                  <label
                    htmlFor="confirm-password"
                    className="text-sm font-medium"
                  >
                    Confirm new password
                  </label>
                  <Input
                    id="confirm-password"
                    type="password"
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    minLength={8}
                  />
                </div>
              </>
            )}
          </CardContent>
          <CardFooter className="flex flex-col gap-2">
            <Button type="submit" className="w-full" disabled={loading}>
              {loading
                ? "Setting password…"
                : needsNewPassword
                  ? "Set password"
                  : "Sign in"}
            </Button>
            {!needsNewPassword && (
              <p className="text-center text-sm text-muted-foreground">
                Don&apos;t have an account?{" "}
                <Link
                  to="/signup"
                  className="underline hover:text-foreground"
                >
                  Sign up
                </Link>
              </p>
            )}
          </CardFooter>
        </form>
      </Card>
    </div>
  )
}
