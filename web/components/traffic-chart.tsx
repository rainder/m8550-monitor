"use client"
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts"

import { formatRate } from "@/lib/format"
import type { HistoryPoint, HistoryRange } from "@/lib/types"

type Props = {
  points: HistoryPoint[]
  range: HistoryRange
  onRangeChange: (r: HistoryRange) => void
}

const RANGES: HistoryRange[] = ["1h", "24h", "7d"]

export function TrafficChart({ points, range, onRangeChange }: Props) {
  const data = points.map((p) => ({
    t: p.ts * 1000,
    rx: p.rxRate,
    tx: p.txRate,
  }))

  const lastRx = [...points].reverse().find((p) => p.rxRate !== null)?.rxRate ?? null
  const lastTx = [...points].reverse().find((p) => p.txRate !== null)?.txRate ?? null

  return (
    <div className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
      <div className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-3">
        <div className="flex items-center gap-6">
          <h2 className="text-[10px] uppercase tracking-[0.18em] text-zinc-500 font-mono">
            Traffic
          </h2>
          <div className="hidden md:flex items-center gap-5 text-[11px] font-mono">
            <Legend swatch="bg-emerald-400" label="Download" value={formatRate(lastRx)} />
            <Legend swatch="bg-blue-400"    label="Upload"   value={formatRate(lastTx)} />
          </div>
        </div>

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

      <div className="h-[280px] px-2 py-3">
        <ResponsiveContainer>
          <AreaChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
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
            <XAxis
              dataKey="t"
              type="number"
              domain={["dataMin", "dataMax"]}
              tickFormatter={(t) =>
                new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
              }
              stroke="#3f3f46"
              tickLine={false}
              axisLine={false}
              fontSize={10}
              fontFamily="var(--font-geist-mono)"
              minTickGap={36}
              tick={{ fill: "#52525b" }}
            />
            <YAxis
              stroke="#3f3f46"
              tickLine={false}
              axisLine={false}
              fontSize={10}
              fontFamily="var(--font-geist-mono)"
              tickFormatter={(v) => formatRate(v)}
              width={64}
              tick={{ fill: "#52525b" }}
            />
            <Tooltip
              cursor={{ stroke: "#27272a", strokeDasharray: "2 2" }}
              contentStyle={{
                background: "#0a0a0a",
                border: "1px solid #27272a",
                borderRadius: "4px",
                fontSize: "11px",
                fontFamily: "var(--font-geist-mono)",
                padding: "8px 10px",
              }}
              labelStyle={{ color: "#a1a1aa", fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.1em" }}
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
