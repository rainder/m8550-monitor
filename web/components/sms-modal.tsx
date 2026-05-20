"use client"

import { useEffect, useState } from "react"

import type { SmsMessage } from "@/lib/types"

type Props = {
  message: SmsMessage
  onClose: () => void
  onMarkRead: (id: number) => void
  onDelete: (id: number) => void
}

export function SmsModal({ message, onClose, onMarkRead, onDelete }: Props) {
  const [pending, setPending] = useState<"read" | "delete" | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  async function handleMarkRead() {
    setPending("read")
    setError(null)
    try {
      const r = await fetch(`/api/sms/${message.id}/read`, { method: "POST" })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      onMarkRead(message.id)
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to mark read")
      setPending(null)
    }
  }

  async function handleHide() {
    setPending("delete")
    setError(null)
    try {
      const r = await fetch(`/api/sms/${message.id}`, { method: "DELETE" })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      onDelete(message.id)
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to hide")
      setPending(null)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="w-full max-w-md max-h-[85vh] flex flex-col rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="sms-modal-title"
      >
        <div className="flex items-start justify-between border-b border-[var(--color-border)] px-5 py-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              {message.unread && (
                <span
                  aria-label="unread"
                  className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400 shrink-0"
                />
              )}
              <h2 id="sms-modal-title" className="truncate text-base text-zinc-100 font-mono">
                {message.sender || "Unknown"}
              </h2>
            </div>
            <p className="mt-1 text-[10px] uppercase tracking-[0.18em] font-mono text-zinc-500 tabular-nums">
              {formatReceivedFull(message.receivedAt)}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="ml-4 -mt-1 -mr-1 rounded p-1 text-zinc-500 hover:bg-white/[0.04] hover:text-zinc-200 focus:outline-none focus:ring-1 focus:ring-zinc-500"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M3 3 L11 11 M11 3 L3 11" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        <div className="overflow-y-auto px-5 py-4 text-sm text-zinc-200 leading-relaxed whitespace-pre-wrap break-words">
          {message.content || <span className="text-zinc-500 italic">(empty message)</span>}
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-[var(--color-border)] px-5 py-3">
          <span className="min-w-0 truncate text-[10px] font-mono text-rose-400">
            {error}
          </span>
          <div className="flex shrink-0 items-center gap-2">
            {message.unread && (
              <button
                type="button"
                onClick={handleMarkRead}
                disabled={pending !== null}
                className="rounded-sm border border-[var(--color-border)] bg-transparent px-2.5 py-1 text-[11px] font-mono uppercase tracking-wider text-zinc-300 transition-colors hover:bg-white/[0.04] hover:text-zinc-100 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {pending === "read" ? "…" : "Mark read"}
              </button>
            )}
            <button
              type="button"
              onClick={handleHide}
              disabled={pending !== null}
              title="Hide from this dashboard. M8550 firmware doesn't support remote delete — the message stays on the router."
              className="rounded-sm border border-rose-500/30 bg-transparent px-2.5 py-1 text-[11px] font-mono uppercase tracking-wider text-rose-300 transition-colors hover:bg-rose-500/10 hover:text-rose-200 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {pending === "delete" ? "…" : "Hide"}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function formatReceivedFull(seconds: number): string {
  if (!seconds) return "—"
  const d = new Date(seconds * 1000)
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, "0")
  const dd = String(d.getDate()).padStart(2, "0")
  const hh = String(d.getHours()).padStart(2, "0")
  const min = String(d.getMinutes()).padStart(2, "0")
  return `${yyyy}-${mm}-${dd} ${hh}:${min}`
}
