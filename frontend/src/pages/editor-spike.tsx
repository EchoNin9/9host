/**
 * T-31a spike page: renders <Puck> with the spike config. Lazy-loaded from App.tsx
 * and only routed when VITE_ENABLE_BLOCK_EDITOR === "true". Publish just logs the data.
 */
import { Puck } from "@puckeditor/core"
import "@puckeditor/core/puck.css"
import { useMemo } from "react"
import { useParams } from "react-router-dom"
import { makeSpikeConfig, spikeSampleData } from "@/editor/puck-config"

export default function EditorSpike() {
  const { siteId } = useParams<{ siteId: string }>()
  const config = useMemo(() => makeSpikeConfig(siteId), [siteId])
  return (
    <div className="h-[calc(100vh-4rem)]">
      <Puck
        config={config}
        data={spikeSampleData}
        onPublish={(data) => console.info("[editor-spike] publish", data)}
      />
    </div>
  )
}
