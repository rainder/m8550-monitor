"use client"
import { useMemo } from "react"
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts"

import { formatRate } from "@/lib/format"
import type { ClientHistoryResponse, HistoryMode, HistoryPoint, HistoryRange } from "@/lib/types"

type Props = {
  // wan-mode data
  points: HistoryPoint[]
  // clients-mode data (null when wan or not yet loaded)
  clientHistory: ClientHistoryResponse | null
  range: HistoryRange
  mode: HistoryMode
  onRangeChange: (r: HistoryRange) => void
  onModeChange: (m: HistoryMode) => void
}

const RANGES: HistoryRange[] = ["1h", "24h", "7d"]
const MODES: { value: HistoryMode; label: string }[] = [
  { value: "wan", label: "WAN" },
  { value: "clients", label: "By Client" },
]

const CLIENT_COLOURS: { stroke: string; fill: string }[] = [
  { stroke: "#4ade80", fill: "#4ade80" },   // emerald
  { stroke: "#60a5fa", fill: "#60a5fa" },   // blue
  { stroke: "#a78bfa", fill: "#a78bfa" },   // violet
  { stroke: "#fbbf24", fill: "#fbbf24" },   // amber
  { stroke: "#fb7185", fill: "#fb7185" },   // rose
  { stroke: "#22d3ee", fill: "#22d3ee" },   // cyan
  { stroke: "#e879f9", fill: "#e879f9" },   // fuchsia
  { stroke: "#bef264", fill: "#bef264" },   // lime
]

export function TrafficChart({ points, clientHistory, range, mode, onRangeChange, onModeChange }: Props) {
  const wanData = useMemo(() => points.map((p) => ({
    t: p.ts * 1000,
    rx: p.rxRate,
    tx: p.txRate,
  })), [points])

  const lastRx = [...points].reverse().find((p) => p.rxRate !== null)?.rxRate ?? null
  const lastTx = [...points].reverse().find((p) => p.txRate !== null)?.txRate ?? null

  // Clients chart data: null → 0 for stack continuity; tooltip shows 0 for missing samples
  const clientChartData = useMemo(() => {
    if (mode !== "clients" || !clientHistory) return []
    return clientHistory.ticks.map((ts, i) => {
      const row: { t: number; [mac: string]: number | null } = { t: ts * 1000 }
      for (const s of clientHistory.series) {
        // Stacked area needs numeric values; treat null as 0 so the stack
        // doesn't break, but tooltip/legend will show null where appropriate.
        row[s.mac] = s.values[i] ?? 0
      }
      return row
    })
  }, [mode, clientHistory])

  const xAxisProps = {
    dataKey: "t" as const,
    type: "number" as const,
    domain: ["dataMin", "dataMax"] as [string, string],
    tickFormatter: (t: number) =>
      new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    stroke: "#3f3f46",
    tickLine: false,
    axisLine: false,
    fontSize: 10,
    fontFamily: "var(--font-geist-mono)",
    minTickGap: 36,
    tick: { fill: "#52525b" },
  }

  const yAxisProps = {
    stroke: "#3f3f46",
    tickLine: false,
    axisLine: false,
    fontSize: 10,
    fontFamily: "var(--font-geist-mono)",
    tickFormatter: (v: number) => formatRate(v),
    width: 64,
    tick: { fill: "#52525b" },
  }

  const tooltipSharedStyle = {
    cursor: { stroke: "#27272a", strokeDasharray: "2 2" },
    contentStyle: {
      background: "#0a0a0a",
      border: "1px solid #27272a",
      borderRadius: "4px",
      fontSize: "11px",
      fontFamily: "var(--font-geist-mono)",
      padding: "8px 10px",
    },
    labelStyle: { color: "#a1a1aa", fontSize: "10px", textTransform: "uppercase" as const, letterSpacing: "0.1em" },
  }

  return (
    <div className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
      <div className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-3">
        <div className="flex items-center gap-6">
          <h2 className="text-[10px] uppercase tracking-[0.18em] text-zinc-500 font-mono">
            Traffic
          </h2>
          {mode === "wan" && (
            <div className="hidden md:flex items-center gap-5 text-[11px] font-mono">
              <Legend swatch="bg-emerald-400" label="Download" value={formatRate(lastRx)} />
              <Legend swatch="bg-blue-400"    label="Upload"   value={formatRate(lastTx)} />
            </div>
          )}
          {mode === "clients" && clientHistory && clientHistory.series.length > 0 && (
            <div className="hidden md:flex items-center gap-4 text-[11px] font-mono flex-wrap">
              {clientHistory.series.slice(0, 5).map((s, i) => {
                const colour = CLIENT_COLOURS[i % CLIENT_COLOURS.length]
                const lastVal = [...s.values].reverse().find((v) => v !== null) ?? null
                return (
                  <div key={s.mac} className="flex items-center gap-2">
                    <span
                      className="block h-1.5 w-1.5 rounded-full"
                      style={{ backgroundColor: colour.stroke }}
                    />
                    <span className="uppercase tracking-wider text-zinc-500">
                      {s.name ?? s.mac}
                    </span>
                    <span className="text-zinc-300 tabular-nums">{formatRate(lastVal)}</span>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Mode selector */}
          <div className="flex items-center gap-px rounded-sm border border-[var(--color-border)] p-px text-[10px] font-mono uppercase tracking-wider">
            {MODES.map((m) => (
              <button
                key={m.value}
                onClick={() => onModeChange(m.value)}
                className={
                  "px-2.5 py-1 rounded-[3px] transition-colors " +
                  (m.value === mode
                    ? "bg-zinc-100 text-zinc-900"
                    : "text-zinc-500 hover:text-zinc-200 hover:bg-white/[0.04]")
                }
              >
                {m.label}
              </button>
            ))}
          </div>

          {/* Range selector */}
          <div className="flex items-center gap-px rounded-sm border border-[var(--color-border)] p-px text-[10px] font-mono uppercase tracking-wider">
            {RANGES.map((r) => (
              <button
                key={r}
                onClick={() => onRangeChange(r)}
                className={
                  "px-2.5 py-1 rounded-[3px] transition-colors " +
                  (r === range
                    ? "bg-zinc-100 text-zinc-900"
                    : "text-zinc-500 hover:text-zinc-200 hover:bg-white/[0.04]")
                }
              >
                {r}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="h-[280px] px-2 py-3">
        <ResponsiveContainer>
          {mode === "wan" ? (
            <AreaChart data={wanData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
              <defs>
                <linearGradient id="rxGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#4ade80" stopOpacity={0.28} />
                  <stop offset="100%" stopColor="#4ade80" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="txGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#60a5fa" stopOpacity={0.22} />
                  <stop offset="100%" stopColor="#60a5fa" stopOpacity={0} />
                </linearGradient>
              </defs>

              <CartesianGrid stroke="#18181b" strokeDasharray="2 4" vertical={false} />
              <XAxis {...xAxisProps} />
              <YAxis {...yAxisProps} />
              <Tooltip
                {...tooltipSharedStyle}
                labelFormatter={(t) => new Date(Number(t)).toLocaleTimeString()}
                formatter={(v, name) => [
                  formatRate(typeof v === "number" ? v : null),
                  name === "rx" ? "↓ Download" : "↑ Upload",
                ]}
              />
              <Area
                type="monotone"
                dataKey="rx"
                stroke="#4ade80"
                strokeWidth={1.5}
                fill="url(#rxGrad)"
                connectNulls={false}
                isAnimationActive={false}
                name="rx"
              />
              <Area
                type="monotone"
                dataKey="tx"
                stroke="#60a5fa"
                strokeWidth={1.5}
                fill="url(#txGrad)"
                connectNulls={false}
                isAnimationActive={false}
                name="tx"
              />
            </AreaChart>
          ) : (
            <AreaChart data={clientChartData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
              <defs>
                {(clientHistory?.series ?? []).map((s, i) => {
                  const colour = CLIENT_COLOURS[i % CLIENT_COLOURS.length]
                  const gradId = `cl-${s.mac.replace(/[:.]/g, "")}`
                  return (
                    <linearGradient key={gradId} id={gradId} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={colour.fill} stopOpacity={0.30} />
                      <stop offset="100%" stopColor={colour.fill} stopOpacity={0} />
                    </linearGradient>
                  )
                })}
              </defs>

              <CartesianGrid stroke="#18181b" strokeDasharray="2 4" vertical={false} />
              <XAxis {...xAxisProps} />
              <YAxis {...yAxisProps} />
              <Tooltip
                {...tooltipSharedStyle}
                labelFormatter={(t) => new Date(Number(t)).toLocaleTimeString()}
                formatter={(v, name) => {
                  const series = clientHistory?.series.find((s) => s.mac === name)
                  return [
                    formatRate(typeof v === "number" ? v : null),
                    series?.name ?? String(name),
                  ]
                }}
              />
              {(clientHistory?.series ?? []).map((s, i) => {
                const colour = CLIENT_COLOURS[i % CLIENT_COLOURS.length]
                return (
                  <Area
                    key={s.mac}
                    type="monotone"
                    dataKey={s.mac}
                    stackId="1"
                    stroke={colour.stroke}
                    fill={`url(#cl-${s.mac.replace(/[:.]/g, "")})`}
                    fillOpacity={1}
                    isAnimationActive={false}
                    name={s.mac}
                  />
                )
              })}
            </AreaChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function Legend({ swatch, label, value }: { swatch: string; label: string; value: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className={`block h-1.5 w-1.5 rounded-full ${swatch}`} />
      <span className="uppercase tracking-wider text-zinc-500">{label}</span>
      <span className="text-zinc-300 tabular-nums">{value}</span>
    </div>
  )
}
