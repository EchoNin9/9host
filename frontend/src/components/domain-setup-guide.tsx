/**
 * Domain Setup Guide (DNS Wizard) — Task 2.81
 * Two paths: Our DNS (CloudNS) vs Own DNS (CNAME + TXT).
 * Shows CNAME target and TXT from API.
 */

import { Copy, Check, Globe, Server } from "lucide-react"
import { useState } from "react"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import type { Domain } from "@/lib/api"

interface DomainSetupGuideProps {
  domain: Domain
  open: boolean
  onOpenChange: (open: boolean) => void
}

function CopyButton({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <Button variant="ghost" size="sm" onClick={copy} className="h-8 px-2">
      {copied ? <Check className="size-4 text-green-600" /> : <Copy className="size-4" />}
      <span className="sr-only">{label}</span>
    </Button>
  )
}

export function DomainSetupGuideDialog({
  domain,
  open,
  onOpenChange,
}: DomainSetupGuideProps) {
  const cname = domain.verification_cname_target
  const txt = domain.verification_txt_record

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle>DNS Setup: {domain.domain}</SheetTitle>
        </SheetHeader>
        <p className="text-sm text-muted-foreground">
          Add these DNS records at your domain provider to connect and verify your domain.
        </p>

        <div className="space-y-6">
          <div>
            <h3 className="text-sm font-medium flex items-center gap-2 mb-2">
              <Globe className="size-4" />
              Own DNS (CNAME + TXT)
            </h3>
            <p className="text-xs text-muted-foreground mb-3">
              Add these records at your DNS provider (e.g. Cloudflare, GoDaddy, Namecheap).
            </p>
            {cname && (
              <div className="rounded-lg border p-3 space-y-1">
                <p className="text-xs font-medium text-muted-foreground">CNAME record</p>
                <div className="flex items-center gap-2">
                  <code className="flex-1 truncate rounded bg-muted px-2 py-1 text-sm">
                    {domain.domain} → {cname}
                  </code>
                  <CopyButton value={`${domain.domain} CNAME ${cname}`} label="Copy CNAME" />
                </div>
                <p className="text-xs text-muted-foreground">
                  Host: <code className="bg-muted px-1">{domain.domain}</code> or @
                </p>
                <p className="text-xs text-muted-foreground">
                  Target: <code className="bg-muted px-1">{cname}</code>
                </p>
              </div>
            )}
            {txt && (
              <div className="rounded-lg border p-3 space-y-1 mt-2">
                <p className="text-xs font-medium text-muted-foreground">TXT record (verification)</p>
                <div className="flex items-center gap-2">
                  <code className="flex-1 truncate rounded bg-muted px-2 py-1 text-sm font-mono">
                    {txt}
                  </code>
                  <CopyButton value={txt} label="Copy TXT" />
                </div>
                <p className="text-xs text-muted-foreground">
                  Host: <code className="bg-muted px-1">_9host-verify.{domain.domain}</code> or @
                </p>
                <p className="text-xs text-muted-foreground">
                  Value: <code className="bg-muted px-1">{txt}</code>
                </p>
              </div>
            )}
            {!cname && !txt && (
              <p className="text-sm text-muted-foreground">
                Verification records will appear after the domain is added.
              </p>
            )}
          </div>

          <div>
            <h3 className="text-sm font-medium flex items-center gap-2 mb-2">
              <Server className="size-4" />
              Our DNS (CloudNS)
            </h3>
            <p className="text-xs text-muted-foreground">
              Transfer your domain to our nameservers and we&apos;ll configure DNS automatically.
              Contact support for nameserver details.
            </p>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
