"use client"

import { useState } from "react"

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
export function ReclaimButton({ online, ageSeconds }: Props) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
      // Leave pending=true; the next /api/current poll will turn `online`
      // back true and the button hides itself. If the reauth fails the
      // collector will log it; the user can try again in 60s.
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
      title="Bypass the 60s auth backoff and reclaim the router session now. Use after closing Tether or the router's own web UI."
      className="rounded-sm border border-amber-500/40 bg-transparent px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider text-amber-300 transition-colors hover:bg-amber-500/10 hover:text-amber-200 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {pending ? "Reclaiming…" : error ? `Retry · ${error}` : "Reclaim"}
    </button>
  )
}
