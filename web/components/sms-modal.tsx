"use client"

import { useEffect } from "react"

import type { SmsMessage } from "@/lib/types"

type Props = {
  message: SmsMessage
  onClose: () => void
}

export function SmsModal({ message, onClose }: Props) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

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
