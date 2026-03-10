"use client"

import { useState } from "react"
import { Link, useLocation, useNavigate } from "react-router-dom"
import { confirmSignUp } from "aws-amplify/auth"
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

export function AuthConfirm() {
  const navigate = useNavigate()
  const location = useLocation()
  const email = (location.state as { email?: string } | null)?.email ?? ""
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
    <div className="flex min-h-screen items-center justify-center p-8">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Confirm your email</CardTitle>
          <CardDescription>
            Enter the verification code sent to {email || "your email"}
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
              <label htmlFor="code" className="text-sm font-medium">
                Verification code
              </label>
              <Input
                id="code"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="123456"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                required
              />
            </div>
          </CardContent>
          <CardFooter className="flex flex-col gap-2">
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Confirming…" : "Confirm"}
            </Button>
            <p className="text-center text-sm text-muted-foreground">
              <Link to="/login" className="underline hover:text-foreground">
                Back to sign in
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>
    </div>
  )
}
