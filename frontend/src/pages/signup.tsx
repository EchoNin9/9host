"use client"

import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { signUp } from "aws-amplify/auth"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { AuthLayout } from "@/components/auth-layout"
import { FormField, Notice } from "@/components/page"

export function Signup() {
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
      await signUp({
        username: email,
        password,
        options: {
          userAttributes: {
            email,
          },
        },
      })
      navigate("/auth/confirm", { state: { email } })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign up failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout
      title="Create your account"
      description="Host your sites on echo9.net, then bring your own domain."
      footer={
        <p>
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-foreground underline underline-offset-4">
            Sign in
          </Link>
        </p>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <Notice tone="danger">{error}</Notice>}
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
        <FormField label="Password" htmlFor="password" hint="At least 8 characters.">
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
        </FormField>
        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? "Creating account…" : "Create account"}
        </Button>
      </form>
    </AuthLayout>
  )
}
