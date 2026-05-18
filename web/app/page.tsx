"use client"

import { useEffect, useState } from "react"

import { ClientModal } from "@/components/client-modal"
import { ClientsTable } from "@/components/clients-table"
import { SignalPanel } from "@/components/signal-panel"
import { SmsPanel } from "@/components/sms-panel"
import { StatCard } from "@/components/stat-card"
import { StatusIndicator } from "@/components/status-indicator"
import { SystemGauges } from "@/components/system-gauges"
import { TrafficChart } from "@/components/traffic-chart"
import { formatBytes, formatRelative } from "@/lib/format"
import type {
  ClientHistoryResponse, CurrentResponse, HistoryMode, HistoryRange,
  HistoryResponse, SmsResponse,
} from "@/lib/types"

const POLL_MS = 5000
const SPARK_WINDOW = 24 // last N history points feed the stat-card sparklines

export default function Page() {
  const [current, setCurrent] = useState<CurrentResponse | null>(null)
  const [history, setHistory] = useState<HistoryResponse | null>(null)
  const [range, setRange] = useState<HistoryRange>("1h")
  const [mode, setMode] = useState<HistoryMode>("wan")
  const [clientHistory, setClientHistory] = useState<ClientHistoryResponse | null>(null)
  const [selectedMac, setSelectedMac] = useState<string | null>(null)
  const [sms, setSms] = useState<SmsResponse | null>(null)

  useEffect(() => {
    let cancelled = false
    async function poll() {
      try {
        const r = await fetch("/api/current", { cache: "no-store" })
        if (!cancelled && r.ok) setCurrent(await r.json())
      } catch {
        /* keep last value on transient blip */
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
        const r = await fetch(`/api/history?range=${range}&mode=wan`, { cache: "no-store" })
        if (!cancelled && r.ok) setHistory(await r.json())
      } catch {
        /* ignore */
      }
    }
    load()
    const id = setInterval(load, POLL_MS * 2)
    return () => { cancelled = true; clearInterval(id) }
  }, [range])

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const r = await fetch("/api/sms", { cache: "no-store" })
        if (!cancelled && r.ok) setSms(await r.json())
      } catch { /* ignore */ }
    }
    load()
    const id = setInterval(load, POLL_MS * 6) // SMS refreshes server-side every ~60s
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  useEffect(() => {
    if (mode !== "clients") return
    let cancelled = false
    async function load() {
      try {
        const r = await fetch(`/api/history?range=${range}&mode=clients`, { cache: "no-store" })
        if (!cancelled && r.ok) setClientHistory(await r.json())
      } catch { /* ignore */ }
    }
    load()
    const id = setInterval(load, POLL_MS * 2)
    return () => { cancelled = true; clearInterval(id) }
  }, [mode, range])

  const sample = current?.sample
  const online = sample?.online ?? false
  const ageSeconds = current?.ageSeconds ?? 0
  const clientCount = current?.clients.length ?? 0

  const points = history?.points ?? []
  const sparkRx = points.slice(-SPARK_WINDOW).map((p) => p.rxRate)
  const sparkTx = points.slice(-SPARK_WINDOW).map((p) => p.txRate)

  return (
    <div className="grain min-h-screen">
      <main className="relative z-10 mx-auto max-w-6xl px-6 py-8 space-y-6">
        <Header
          online={online}
          ageSeconds={ageSeconds}
          clientCount={clientCount}
          cpuPct={sample?.cpuPct ?? null}
          memPct={sample?.memPct ?? null}
          smsUnread={sms?.unreadCount ?? 0}
        />

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <StatCard label="Download" rate={sample?.rxRate ?? null} sparkValues={sparkRx} accent="down" />
          <StatCard label="Upload"   rate={sample?.txRate ?? null} sparkValues={sparkTx} accent="up" />
          <SignalPanel sample={sample ?? null} />
        </div>

        <div className="flex items-center justify-end gap-2 text-[11px] font-mono text-zinc-500">
          <span className="uppercase tracking-wider">Total</span>
          <span className="text-zinc-300 tabular-nums">
            {formatBytes(sample?.totalBytes ?? null)}
          </span>
          <span>used</span>
        </div>

        <TrafficChart
          points={points}
          clientHistory={clientHistory}
          range={range}
          mode={mode}
          onRangeChange={setRange}
          onModeChange={setMode}
        />

        <ClientsTable
          clients={current?.clients ?? []}
          onClientClick={(c) => setSelectedMac(c.mac)}
        />

        {sms && (
          <SmsPanel
            messages={sms.messages}
            unreadCount={sms.unreadCount}
            syncedAt={sms.syncedAt}
          />
        )}

        <Footer />
      </main>

      {selectedMac && (() => {
        const live = current?.clients.find((c) => c.mac === selectedMac)
        if (!live) return null
        return <ClientModal client={live} onClose={() => setSelectedMac(null)} />
      })()}
    </div>
  )
}

function Header({
  online, ageSeconds, clientCount, cpuPct, memPct, smsUnread,
}: {
  online: boolean
  ageSeconds: number
  clientCount: number
  cpuPct: number | null
  memPct: number | null
  smsUnread: number
}) {
  return (
    <header className="flex items-center justify-between border-b border-[var(--color-border)] pb-5">
      <div className="flex items-baseline gap-3">
        <div className="flex items-center gap-2">
          {/* logomark: small geometric tile */}
          <span className="block h-4 w-4 rounded-sm bg-zinc-50 relative overflow-hidden">
            <span className="absolute inset-x-0 bottom-0 h-1 bg-emerald-400" />
            <span className="absolute inset-x-0 top-0 h-px bg-blue-400" />
          </span>
          <span className="font-mono text-sm tracking-tight text-zinc-50">m8550</span>
        </div>
        <span className="text-zinc-700">/</span>
        <span className="text-[11px] uppercase tracking-[0.18em] text-zinc-500 font-mono">
          Operations
        </span>
      </div>

      <div className="flex items-center gap-5">
        <SystemGauges cpuPct={cpuPct} memPct={memPct} />
        <Metric label="Clients" value={String(clientCount)} />
        {smsUnread > 0 && <Metric label="SMS" value={`${smsUnread} new`} accent />}
        <Metric label="Updated" value={formatRelative(ageSeconds)} />
        <StatusIndicator online={online} ageSeconds={ageSeconds} />
      </div>
    </header>
  )
}

function Metric({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="hidden sm:flex items-center gap-2 text-[11px] font-mono">
      <span className="uppercase tracking-wider text-zinc-600">{label}</span>
      <span className={`tabular-nums ${accent ? "text-emerald-300" : "text-zinc-300"}`}>
        {value}
      </span>
    </div>
  )
}

function Footer() {
  return (
    <footer className="flex items-center justify-between border-t border-[var(--color-border)] pt-4 text-[10px] uppercase tracking-[0.18em] text-zinc-600 font-mono">
      <span>192.168.1.1 · TPLink M8550 · poll 5s</span>
      <span>local · v0.1</span>
    </footer>
  )
}
