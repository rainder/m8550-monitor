"use client"

import { useState } from "react"

import { SmsModal } from "@/components/sms-modal"
import type { SmsMessage } from "@/lib/types"

type Props = {
  messages: SmsMessage[]
  unreadCount: number
  syncedAt: number   // unix seconds; 0 when never synced
  onMarkRead: (id: number) => void
  onDelete: (id: number) => void
}

export function SmsPanel({ messages, unreadCount, syncedAt, onMarkRead, onDelete }: Props) {
  const [openId, setOpenId] = useState<number | null>(null)

  if (syncedAt === 0 && messages.length === 0) {
    // Never synced yet — silently hide so old DBs don't render an empty section.
    return null
  }

  const open = openId !== null ? messages.find((m) => m.id === openId) ?? null : null

  return (
    <>
      <Section count={messages.length} unreadCount={unreadCount}>
        {messages.length === 0 ? (
          <div className="px-5 py-8 text-center text-xs text-zinc-500 font-mono">
            Inbox empty
          </div>
        ) : (
          <ul className="divide-y divide-[var(--color-border)]">
            {messages.map((m) => (
              <SmsRow
                key={m.id}
                message={m}
                onClick={() => setOpenId(m.id)}
              />
            ))}
          </ul>
        )}
      </Section>
      {open && (
        <SmsModal
          message={open}
          onClose={() => setOpenId(null)}
          onMarkRead={onMarkRead}
          onDelete={onDelete}
        />
      )}
    </>
  )
}

function SmsRow({ message, onClick }: { message: SmsMessage; onClick: () => void }) {
  return (
    <li
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault()
          onClick()
        }
      }}
      className="px-5 py-3 text-sm cursor-pointer transition-colors hover:bg-white/[0.02] focus:outline-none focus:bg-white/[0.04]"
    >
      <div className="flex items-baseline justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          {message.unread && (
            <span
              aria-label="unread"
              className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400 shrink-0"
            />
          )}
          <span className={`truncate font-mono ${message.unread ? "text-zinc-100" : "text-zinc-300"}`}>
            {message.sender || "Unknown"}
          </span>
        </div>
        <span className="font-mono text-[11px] text-zinc-500 tabular-nums shrink-0">
          {formatReceivedAt(message.receivedAt)}
        </span>
      </div>
      <div className="mt-1 text-[12px] text-zinc-400 leading-relaxed line-clamp-2 break-words">
        {message.content}
      </div>
    </li>
  )
}

function Section({
  count, unreadCount, children,
}: {
  count: number
  unreadCount: number
  children: React.ReactNode
}) {
  return (
    <div className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
      <div className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-3">
        <div className="flex items-center gap-2">
          <h2 className="text-[10px] uppercase tracking-[0.18em] text-zinc-500 font-mono">
            SMS
          </h2>
          {unreadCount > 0 && (
            <span className="rounded-sm bg-emerald-500/20 px-1.5 py-0.5 text-[10px] font-mono text-emerald-300 tabular-nums">
              {unreadCount} new
            </span>
          )}
        </div>
        <span className="text-[11px] text-zinc-600 tabular-nums font-mono">
          {count} total
        </span>
      </div>
      {children}
    </div>
  )
}

function formatReceivedAt(seconds: number): string {
  if (!seconds) return "—"
  const d = new Date(seconds * 1000)
  const now = new Date()
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  const hh = String(d.getHours()).padStart(2, "0")
  const mm = String(d.getMinutes()).padStart(2, "0")
  if (sameDay) return `${hh}:${mm}`
  const month = String(d.getMonth() + 1).padStart(2, "0")
  const day = String(d.getDate()).padStart(2, "0")
  return `${month}-${day} ${hh}:${mm}`
}
