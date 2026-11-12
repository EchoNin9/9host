"use client"

import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { signIn, confirmSignIn } from "aws-amplify/auth"
import { Hub } from "aws-amplify/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { AuthLayout } from "@/components/auth-layout"
import { FormField, Notice } from "@/components/page"
import { clearSiteToken, fetchAllTenants, fetchTenants, getToken } from "@/lib/api"

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
    // A Cognito sign-in ends any site-login (TUSER) session: the auth modes never mix.
    clearSiteToken()
    try {
      const token = await getToken("cognito")
      if (!token) return "/"

      const { isSuperadmin } = await fetchAllTenants(token)
      if (isSuperadmin) return "/admin"

      const tenants = await fetchTenants(token)
      if (tenants.length >= 1) return `/${tenants[0].slug}`
      return "/"
    } catch {
      return "/"
    }
  }

  return (
    <AuthLayout
      title={needsNewPassword ? "Set a new password" : "Sign in"}
      description={
        needsNewPassword
          ? "Your account requires a new password before you continue."
          : "Manage your sites, domains and team."
      }
      footer={
        !needsNewPassword && (
          <>
            <p>
              No account yet?{" "}
              <Link to="/signup" className="font-medium text-foreground underline underline-offset-4">
                Create one
              </Link>
            </p>
            <p>
              Have a site username instead?{" "}
              <Link to="/login/site" className="font-medium text-foreground underline underline-offset-4">
                Site sign-in
              </Link>
            </p>
          </>
        )
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <Notice tone="danger">{error}</Notice>}
        {!needsNewPassword ? (
          <>
            <FormField label="Email" htmlFor="email">
              <Input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
              />
            </FormField>
            <FormField label="Password" htmlFor="password">
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </FormField>
          </>
        ) : (
          <>
            <FormField label="New password" htmlFor="new-password" hint="At least 8 characters.">
              <Input
                id="new-password"
                type="password"
                autoComplete="new-password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={8}
                autoFocus
              />
            </FormField>
            <FormField label="Confirm new password" htmlFor="confirm-password">
              <Input
                id="confirm-password"
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={8}
              />
            </FormField>
          </>
        )}
        <Button type="submit" className="w-full" disabled={loading}>
          {needsNewPassword
            ? loading
              ? "Setting password…"
              : "Set password"
            : loading
              ? "Signing in…"
              : "Sign in"}
        </Button>
      </form>
    </AuthLayout>
  )
}
