"use client"

import { useEffect, useState } from "react"

import { Sparkline } from "@/components/sparkline"
import { formatBytes, formatRate } from "@/lib/format"
import type { Client, ClientHistoryResponse } from "@/lib/types"

type Props = {
  client: Client
  onClose: () => void
}

const BAND_LABEL: Record<Client["connType"], string> = {
  host_2g: "2.4 GHz Wi-Fi",
  host_5g: "5 GHz Wi-Fi",
  wired: "Wired",
}

const BAND_ACCENT: Record<Client["connType"], string> = {
  host_2g: "text-amber-300",
  host_5g: "text-emerald-300",
  wired: "text-zinc-300",
}

export function ClientModal({ client, onClose }: Props) {
  const series = useClientSeries(client.mac)

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
        className="w-full max-w-md rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="client-modal-title"
      >
        <div className="flex items-start justify-between border-b border-[var(--color-border)] px-5 py-4">
          <div className="min-w-0">
            <h2
              id="client-modal-title"
              className="truncate text-base text-zinc-100 font-mono"
            >
              {client.name ?? "Unknown device"}
            </h2>
            <p className={`mt-1 text-[10px] uppercase tracking-[0.18em] font-mono ${BAND_ACCENT[client.connType]}`}>
              {BAND_LABEL[client.connType]}
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

        <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-3 px-5 py-4 text-sm">
          <Field label="IP">{client.ip ?? "—"}</Field>
          <Field label="MAC">{client.mac}</Field>
          <Field label="Bandwidth">{formatRate(client.bandwidth)}</Field>
          <Field label="Total used">{formatBytes(client.totalBytes)}</Field>
        </dl>

        <div className="border-t border-[var(--color-border)] px-5 py-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] uppercase tracking-[0.18em] text-zinc-500 font-mono">
              Bandwidth · 1h
            </span>
            {series && series.length >= 2 && (
              <span className="text-[10px] font-mono text-zinc-500 tabular-nums">
                peak {formatRate(peakOf(series))}
              </span>
            )}
          </div>
          {series === null ? (
            <div className="h-14 flex items-center text-[11px] font-mono text-zinc-600">
              Loading…
            </div>
          ) : series.length < 2 ? (
            <div className="h-14 flex items-center text-[11px] font-mono text-zinc-600">
              Not enough history yet
            </div>
          ) : (
            <Sparkline
              values={series}
              stroke="#34d399"
              width={400}
              height={56}
            />
          )}
        </div>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <>
      <dt className="text-[10px] uppercase tracking-[0.18em] text-zinc-500 font-mono self-center">
        {label}
      </dt>
      <dd className="text-zinc-100 font-mono text-xs tabular-nums break-all">
        {children}
      </dd>
    </>
  )
}

function peakOf(values: (number | null)[]): number | null {
  let max: number | null = null
  for (const v of values) {
    if (v === null) continue
    if (max === null || v > max) max = v
  }
  return max
}

/** Fetches 1h client-history for the given MAC. `null` while loading, `[]` when not found. */
function useClientSeries(mac: string): (number | null)[] | null {
  const [series, setSeries] = useState<(number | null)[] | null>(null)

  useEffect(() => {
    let cancelled = false
    setSeries(null)
    async function load() {
      try {
        const r = await fetch("/api/history?range=1h&mode=clients", { cache: "no-store" })
        if (!r.ok) {
          if (!cancelled) setSeries([])
          return
        }
        const data: ClientHistoryResponse = await r.json()
        const found = data.series.find((s) => s.mac === mac)
        if (!cancelled) setSeries(found?.values ?? [])
      } catch {
        if (!cancelled) setSeries([])
      }
    }
    load()
    return () => { cancelled = true }
  }, [mac])

  return series
}
