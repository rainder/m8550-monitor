"use client"

import { useEffect, useState } from "react"

type Props = {
  online: boolean
  ageSeconds: number
}

/**
 * Shown when the router is offline (or seriously stale): a small button that
 * tells the collector to bypass its session-contention backoff and try to
 * reclaim the router session right now. Useful when the user has just closed
 * Tether / the router web UI and wants the dashboard to recover without
 * waiting out the 60s cooldown.
 */
// Collector picks the action up within ~1s; a login round-trip plus the next
// snapshot and the 5s /api/current poll fit comfortably inside this.
const RECLAIM_TIMEOUT_MS = 30_000

export function ReclaimButton({ online, ageSeconds }: Props) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // The collector consumes the action fire-and-forget, so we only learn of
  // success via `online` flipping back. If it hasn't within this window the
  // reclaim failed (usually: another session still holds the router's only
  // slot) — stop spinning and let the user retry.
  useEffect(() => {
    if (!pending) return
    if (online) {
      setPending(false)
      return
    }
    const t = setTimeout(() => {
      setPending(false)
      setError("still offline")
    }, RECLAIM_TIMEOUT_MS)
    return () => clearTimeout(t)
  }, [pending, online])

  // Only worth showing while data isn't flowing. 60s tolerates one or two
  // missed ticks before nagging — matches the auth backoff window.
  const show = !online || ageSeconds > 60
  if (!show) return null

  async function handleClick() {
    setPending(true)
    setError(null)
    try {
      const r = await fetch("/api/router/reauth", { method: "POST" })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      // Leave pending=true; the effect above resolves it.
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed")
      setPending(false)
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={pending}
      title={error
        ? "Router still refused the login — another session (Tether, the router web UI) probably holds its only slot. Close it and retry."
        : "Bypass the 60s auth backoff and reclaim the router session now. Use after closing Tether or the router's own web UI."}
      className="rounded-sm border border-amber-500/40 bg-transparent px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider text-amber-300 transition-colors hover:bg-amber-500/10 hover:text-amber-200 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {pending ? "Reclaiming…" : error ? `Retry · ${error}` : "Reclaim"}
    </button>
  )
}
