"use client"
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
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

  return (
    <div className="bg-zinc-900 rounded-lg p-5 border border-zinc-800 space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-xs uppercase tracking-wider text-zinc-500">Traffic</div>
        <div className="flex gap-1">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => onRangeChange(r)}
              className={`px-2 py-1 text-xs rounded ${
                r === range ? "bg-zinc-700 text-zinc-100" : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      <div className="h-64">
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 10, right: 10, bottom: 10, left: 10 }}>
            <CartesianGrid stroke="#27272a" />
            <XAxis
              dataKey="t"
              type="number"
              domain={["dataMin", "dataMax"]}
              tickFormatter={(t) =>
                new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
              }
              stroke="#71717a"
              fontSize={11}
            />
            <YAxis
              stroke="#71717a"
              fontSize={11}
              tickFormatter={(v) => formatRate(v)}
            />
            <Tooltip
              contentStyle={{ background: "#18181b", border: "1px solid #3f3f46" }}
              labelFormatter={(t) => new Date(Number(t)).toLocaleTimeString()}
              formatter={(v) => formatRate(typeof v === "number" ? v : null)}
            />
            <Line type="monotone" dataKey="rx" stroke="#22c55e" dot={false} connectNulls={false} name="↓" />
            <Line type="monotone" dataKey="tx" stroke="#3b82f6" dot={false} connectNulls={false} name="↑" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
