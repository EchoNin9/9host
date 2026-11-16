/**
 * Domain Setup Guide (DNS wizard) — Cloudflare for SaaS custom hostnames.
 * The tenant first adds the _9host-verify TXT ownership record (SEC-05), then CNAMEs for the
 * apex and www → proxy.echonin9.com, plus any TXT records Cloudflare asks for. Rendered inside the
 * custom_domains FeatureGate on the Domains page.
 */

import { Copy, Check, Globe, Server, ShieldCheck } from "lucide-react"
import { useState } from "react"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import type { Domain } from "@/lib/api"

const PROXY_CNAME_TARGET = "proxy.echonin9.com"

interface DomainSetupGuideProps {
  domain: Domain
  open: boolean
  onOpenChange: (open: boolean) => void
}

function CopyButton({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    void navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <Button variant="ghost" size="sm" onClick={copy} className="h-8 px-2">
      {copied ? <Check className="size-4 text-success" /> : <Copy className="size-4" />}
      <span className="sr-only">{label}</span>
    </Button>
  )
}

function RecordField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}:</p>
      <div className="flex items-center gap-2">
        <code className="flex-1 truncate rounded bg-muted px-2 py-1 text-xs font-mono">{value}</code>
        <CopyButton value={value} label={`Copy ${label.toLowerCase()}`} />
      </div>
    </div>
  )
}

export function DomainSetupGuideDialog({
  domain,
  open,
  onOpenChange,
}: DomainSetupGuideProps) {
  const target = domain.cname_target || PROXY_CNAME_TARGET
  const txtRecords = domain.validation_records ?? []
  const hosts = [domain.domain, ...(domain.www_domain ? [domain.www_domain] : [])]
  const isActive = domain.status === "ACTIVE"

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>DNS Setup: {domain.domain}</SheetTitle>
        </SheetHeader>
        <p className="text-sm text-muted-foreground">
          Add these records at your DNS provider. We provision the domain once the ownership TXT
          record resolves; SSL is issued automatically after that.
        </p>

        <div className="space-y-6">
          <div>
            <h3 className="text-sm font-medium flex items-center gap-2 mb-2">
              <ShieldCheck className="size-4" />
              Step 1: Ownership & validation (TXT)
            </h3>
            {txtRecords.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                {isActive
                  ? "No validation records needed — this domain is active."
                  : "Validation records will appear here once Cloudflare issues them."}
              </p>
            ) : (
              txtRecords.map((rec) => (
                <div key={`${rec.name}:${rec.value}`} className="rounded-lg border p-3 space-y-2 mt-2">
                  <p className="text-xs font-medium text-muted-foreground">
                    TXT record ({rec.purpose === "ssl" ? "SSL certificate" : "domain ownership"})
                  </p>
                  <RecordField label="Name" value={rec.name} />
                  <RecordField label="Value" value={rec.value} />
                </div>
              ))
            )}
          </div>

          <div>
            <h3 className="text-sm font-medium flex items-center gap-2 mb-2">
              <Globe className="size-4" />
              Step 2: Point your domain
            </h3>
            {hosts.map((host, i) => (
              <div key={host} className="rounded-lg border p-3 space-y-2 mt-2">
                <p className="text-xs font-medium text-muted-foreground">
                  {i === 0 ? "ALIAS / ANAME record (apex — CNAME isn't allowed here; or CNAME flattening)" : "CNAME record"}
                </p>
                <RecordField label="Name" value={host} />
                <RecordField label="Target" value={target} />
              </div>
            ))}
          </div>

          <div className="rounded-lg border p-3 text-xs space-y-1">
            <p>
              Status: <strong>{isActive ? "Active" : "Pending validation"}</strong>
              {domain.cf_status && <> · hostname {domain.cf_status}</>}
              {domain.ssl_status && <> · SSL {domain.ssl_status}</>}
              {domain.www_domain && <> · www {domain.www_status === "ACTIVE" ? "active" : "pending"}</>}
            </p>
            {domain.verification_errors?.map((err) => (
              <p key={err} className="text-destructive">{err}</p>
            ))}
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
