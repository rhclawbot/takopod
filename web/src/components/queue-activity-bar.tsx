import { useState, useEffect } from "react"
import { ChevronDown, ChevronRight, FileCode, MessageSquare, Terminal, X } from "lucide-react"
import type { QueueStatusFrame } from "@/lib/types"

function formatElapsed(createdAt: string): string {
  const ts = new Date(createdAt).getTime()
  if (isNaN(ts)) return ""
  const elapsed = Math.max(0, Math.floor((Date.now() - ts) / 1000))
  if (elapsed < 60) return `${elapsed}s`
  const mins = Math.floor(elapsed / 60)
  const secs = elapsed % 60
  return `${mins}m${secs > 0 ? ` ${secs}s` : ""}`
}

function summarizeItems(status: QueueStatusFrame): string {
  const items = status.items ?? []
  if (items.length === 0) {
    const parts: string[] = []
    if (status.in_flight > 0) parts.push(`${status.in_flight} in-flight`)
    if (status.queued > 0) parts.push(`${status.queued} queued`)
    return parts.join(", ")
  }

  const scripts = items.filter((i) => i.payload_type === "run_script")
  const messages = items.filter((i) => i.payload_type === "user_message")
  const other = items.length - scripts.length - messages.length

  const parts: string[] = []
  if (scripts.length > 0) {
    const running = scripts.filter((s) => s.status === "IN-FLIGHT").length
    const queued = scripts.length - running
    if (running > 0) parts.push(`${running} script${running > 1 ? "s" : ""} running`)
    if (queued > 0) parts.push(`${queued} script${queued > 1 ? "s" : ""} queued`)
  }
  if (messages.length > 0) {
    const inflight = messages.filter((m) => m.status === "IN-FLIGHT").length
    const queued = messages.length - inflight
    if (inflight > 0) parts.push(`${inflight} message${inflight > 1 ? "s" : ""} processing`)
    if (queued > 0) parts.push(`${queued} message${queued > 1 ? "s" : ""} queued`)
  }
  if (other > 0) parts.push(`${other} other`)

  return parts.join(", ")
}

function ItemIcon({ type }: { type: string }) {
  if (type === "run_script") return <FileCode className="size-3 text-muted-foreground" />
  if (type === "user_message") return <MessageSquare className="size-3 text-muted-foreground" />
  return <Terminal className="size-3 text-muted-foreground" />
}

function itemLabel(item: { payload_type: string; script?: string | null; command?: string | null; preview?: string | null }): string {
  if (item.payload_type === "run_script" && item.script) {
    const parts = item.script.split("/")
    return parts[parts.length - 1]
  }
  if (item.payload_type === "user_message") {
    if (item.preview) return item.preview
    return "User message"
  }
  if (item.payload_type === "system_command") {
    if (item.command === "shutdown") return "System command: shutdown"
    if (item.command === "clear_context") return "System command: clear context"
    return "System command"
  }
  return item.payload_type
}

export function QueueActivityBar({ status, onDeleteItem }: { status: QueueStatusFrame; onDeleteItem?: (itemId: string) => void }) {
  const [expanded, setExpanded] = useState(false)
  const [, tick] = useState(0)
  const items = status.items ?? []
  const hasDetails = items.length > 0

  useEffect(() => {
    if (!expanded || items.length === 0) return
    const id = setInterval(() => tick((n) => n + 1), 1000)
    return () => clearInterval(id)
  }, [expanded, items.length])

  return (
    <div className="border-t text-xs text-muted-foreground">
      <button
        onClick={() => hasDetails && setExpanded(!expanded)}
        className={`flex w-full items-center gap-2 px-4 py-2 ${hasDetails ? "cursor-pointer hover:bg-muted/50" : "cursor-default"}`}
      >
        <span className="inline-block size-2 animate-pulse rounded-full bg-primary" />
        <span className="flex-1 text-left">{summarizeItems(status)}</span>
        {hasDetails && (
          expanded
            ? <ChevronDown className="size-3" />
            : <ChevronRight className="size-3" />
        )}
      </button>
      {expanded && items.length > 0 && (
        <div className="border-t px-4 py-1.5 space-y-1">
          {items.map((item) => (
            <div key={item.message_id} className="flex items-center gap-2 py-0.5">
              <ItemIcon type={item.payload_type} />
              <span className="flex-1 truncate">{itemLabel(item)}</span>
              <span className="tabular-nums text-[10px]">{formatElapsed(item.created_at)}</span>
              <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                item.status === "IN-FLIGHT"
                  ? "bg-primary/10 text-primary"
                  : "bg-muted text-muted-foreground"
              }`}>
                {item.status === "IN-FLIGHT" ? "running" : "queued"}
              </span>
              {onDeleteItem && (
                <button
                  onClick={(e) => { e.stopPropagation(); onDeleteItem(item.message_id) }}
                  className="rounded p-0.5 hover:bg-destructive/10 hover:text-destructive"
                >
                  <X className="size-3" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
