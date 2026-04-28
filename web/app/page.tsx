"use client"

import { useEffect, useState } from "react"

import { ClientsTable } from "@/components/clients-table"
import { RateCard } from "@/components/rate-card"
import { StatusPill } from "@/components/status-pill"
import { TrafficChart } from "@/components/traffic-chart"
import type { CurrentResponse, HistoryRange, HistoryResponse } from "@/lib/types"

const POLL_MS = 5000

export default function Page() {
  const [current, setCurrent] = useState<CurrentResponse | null>(null)
  const [history, setHistory] = useState<HistoryResponse | null>(null)
  const [range, setRange] = useState<HistoryRange>("1h")

  useEffect(() => {
    let cancelled = false
    async function poll() {
      try {
        const r = await fetch("/api/current", { cache: "no-store" })
        if (!cancelled && r.ok) setCurrent(await r.json())
      } catch {
        // network blip; just keep last value
      }
    }
    poll()
    const id = setInterval(poll, POLL_MS)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const r = await fetch(`/api/history?range=${range}`, { cache: "no-store" })
        if (!cancelled && r.ok) setHistory(await r.json())
      } catch {
        // ignore
      }
    }
    load()
    const id = setInterval(load, POLL_MS * 2)
    return () => { cancelled = true; clearInterval(id) }
  }, [range])

  const sample = current?.sample
  const online = sample?.online ?? false
  const ageSeconds = current?.ageSeconds ?? 0
  const clientCount = current?.clients.length ?? 0

  return (
    <main className="max-w-5xl mx-auto p-6 space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">M8550 Monitor</h1>
        <div className="flex items-center gap-3 text-sm text-zinc-400">
          <span>{clientCount} {clientCount === 1 ? "client" : "clients"}</span>
          <StatusPill online={online} ageSeconds={ageSeconds} />
        </div>
      </header>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <RateCard label="Download" rate={sample?.rxRate ?? null} arrow="↓" />
        <RateCard label="Upload" rate={sample?.txRate ?? null} arrow="↑" />
      </div>

      <TrafficChart
        points={history?.points ?? []}
        range={range}
        onRangeChange={setRange}
      />

      <ClientsTable clients={current?.clients ?? []} />
    </main>
  )
}
