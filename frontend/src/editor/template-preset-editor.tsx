/**
 * Puck editor for one template preset doc (T-32b, ADR-0003 §5). Same block config as the
 * site page editor (T-31); the component list is limited to the template's allowed blocks,
 * and the canvas iframe loads the base renderer CSS plus the draft tokens as --template-*.
 * Lazy-loaded by the template editor page so Puck stays out of the admin chunk when unused.
 */
import { Puck, type Config, type Data } from "@puckeditor/core"
import "@puckeditor/core/puck.css"
import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import type { BlockDoc } from "@/editor/block-env"
import { makeBlockConfig, PUCK_UI, PUCK_VIEWPORTS, toDoc, toPuckData } from "@/editor/puck-config"

const TokensCssContext = createContext("")

function CanvasStyles({ doc, href, children }: { doc?: Document; href: string; children: ReactNode }) {
  const tokensCss = useContext(TokensCssContext)
  const styleRef = useRef<HTMLStyleElement | null>(null)
  useEffect(() => {
    if (!doc) return
    const link = doc.createElement("link")
    link.rel = "stylesheet"
    link.href = href
    const s = doc.createElement("style")
    doc.head.append(link, s)
    styleRef.current = s
    return () => {
      link.remove()
      s.remove()
      styleRef.current = null
    }
  }, [doc, href])
  // Runs after the effect above, so the <style> exists; tokens update live without remounting.
  useEffect(() => {
    if (styleRef.current) styleRef.current.textContent = tokensCss
  }, [doc, href, tokensCss])
  return <>{children}</>
}

export default function TemplatePresetEditor({
  doc,
  onChange,
  cssHref,
  tokensCss,
  allowedBlocks,
  title,
  path,
}: {
  doc: BlockDoc
  onChange: (doc: BlockDoc) => void
  cssHref: string
  tokensCss: string
  allowedBlocks: string[]
  title: string
  path: string
}) {
  // Puck owns the data after mount; the parent remounts it (key) per preset/version.
  const [initial] = useState<Data>(() => toPuckData(doc))
  const allowedKey = allowedBlocks.join(",")
  const config = useMemo(() => {
    const c = makeBlockConfig()
    // Only allowed blocks are offered; blocks already in the preset still render.
    c.categories = { allowed: { title: "Blocks", components: allowedKey ? allowedKey.split(",") : [] }, other: { visible: false } }
    return c as Config
  }, [allowedKey])
  const overrides = useMemo(
    () => ({
      iframe: ({ children, document }: { children: ReactNode; document?: Document }) => (
        <CanvasStyles doc={document} href={cssHref}>
          {children}
        </CanvasStyles>
      ),
      headerActions: () => <></>,
    }),
    [cssHref]
  )
  return (
    <TokensCssContext.Provider value={tokensCss}>
      <Puck
        config={config}
        data={initial}
        onChange={(d) => onChange(toDoc(d))}
        overrides={overrides}
        iframe={{ enabled: true }}
        viewports={PUCK_VIEWPORTS}
        ui={PUCK_UI}
        headerTitle={title}
        headerPath={path}
        height="100%"
      />
    </TokensCssContext.Provider>
  )
}
