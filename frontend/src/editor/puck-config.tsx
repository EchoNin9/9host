/**
 * T-31a spike: minimal Puck config (ADR-0003). Two blocks only.
 * RichText uses our existing TipTap RichTextEditor as a Puck custom field,
 * so the prose editor (and its media picker) is shared with the legacy page editor.
 */
import type { Config, Data } from "@puckeditor/core"
import { RichTextEditor } from "@/components/ui/rich-text-editor"

type HeadingProps = { text: string; level: "h1" | "h2" | "h3" }
type RichTextProps = { html: string }

export type SpikeComponents = { Heading: HeadingProps; RichText: RichTextProps }

export function makeSpikeConfig(siteId?: string): Config<SpikeComponents> {
  return {
    components: {
      Heading: {
        fields: {
          text: { type: "text" },
          level: {
            type: "select",
            options: [
              { label: "H1", value: "h1" },
              { label: "H2", value: "h2" },
              { label: "H3", value: "h3" },
            ],
          },
        },
        defaultProps: { text: "Heading", level: "h2" },
        render: ({ text, level }) => {
          const Tag = level
          return <Tag className="b-heading">{text}</Tag>
        },
      },
      RichText: {
        fields: {
          html: {
            type: "custom",
            label: "Content",
            render: ({ value, onChange }) => (
              <RichTextEditor value={value ?? ""} onChange={onChange} siteId={siteId} />
            ),
          },
        },
        defaultProps: { html: "<p>Write something…</p>" },
        // Spike only: the canvas trusts TipTap output. The real build sanitizes on save
        // and on compile (ADR-0003 §3).
        render: ({ html }) => <div className="content" dangerouslySetInnerHTML={{ __html: html }} />,
      },
    },
  }
}

export const spikeSampleData: Data<SpikeComponents> = {
  root: { props: {} },
  content: [
    { type: "Heading", props: { id: "b1", text: "We are Acme", level: "h1" } },
    {
      type: "RichText",
      props: { id: "b2", html: "<p>Hello from <strong>TipTap</strong> inside <em>Puck</em>.</p>" },
    },
  ],
}
