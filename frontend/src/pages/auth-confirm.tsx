"use client"

import { useState } from "react"
import { Link, useLocation, useNavigate } from "react-router-dom"
import { confirmSignUp } from "aws-amplify/auth"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { AuthLayout } from "@/components/auth-layout"
import { FormField, Notice } from "@/components/page"

export function AuthConfirm() {
  const navigate = useNavigate()
  const location = useLocation()
  const stateEmail = (location.state as { email?: string } | null)?.email ?? ""
  // Opened directly (e.g. from the email link or a reload) there is no router state: ask for it.
  const [email, setEmail] = useState(stateEmail)
  const [code, setCode] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await confirmSignUp({
        username: email,
        confirmationCode: code,
      })
      navigate("/login", { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Confirmation failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout
      title="Confirm your email"
      description={
        stateEmail ? (
          <>
            Enter the verification code we sent to <span className="font-medium text-foreground">{stateEmail}</span>.
          </>
        ) : (
          "Enter your email and the verification code we sent you."
        )
      }
      footer={
        <p>
          <Link to="/login" className="font-medium text-foreground underline underline-offset-4">
            Back to sign in
          </Link>
        </p>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <Notice tone="danger">{error}</Notice>}
        {!stateEmail && (
          <FormField label="Email" htmlFor="confirm-email">
            <Input
              id="confirm-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </FormField>
        )}
        <FormField label="Verification code" htmlFor="code">
          <Input
            id="code"
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            placeholder="123456"
            className="font-mono tracking-[0.3em]"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            required
            autoFocus={!!stateEmail}
          />
        </FormField>
        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? "Confirming…" : "Confirm email"}
        </Button>
      </form>
    </AuthLayout>
  )
}
