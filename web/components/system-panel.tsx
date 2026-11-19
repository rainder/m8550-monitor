import type { HistoryPoint, HistoryRange } from "@/lib/types"

import { Sparkline } from "./sparkline"

type Props = {
  cpuPct: number | null
  memPct: number | null
  points: HistoryPoint[]
  range: HistoryRange
}

/**
 * Router CPU / memory utilisation: live value plus avg / peak and a trend
 * line over the currently selected history range. Values are 0..1 fractions
 * straight from the firmware's `cpu_usage` / `mem_usage`.
 */
export function SystemPanel({ cpuPct, memPct, points, range }: Props) {
  return (
    <div className="relative overflow-hidden rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-violet-500/40 to-transparent" />

      <div className="flex items-center justify-between mb-4">
        <span className="text-[10px] uppercase tracking-[0.18em] text-zinc-500 font-mono">
          System
        </span>
        <span className="text-[10px] uppercase tracking-[0.18em] text-zinc-600 font-mono">
          {range}
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        <Metric
          label="CPU"
          current={cpuPct}
          series={points.map((p) => p.cpuPct)}
          stroke="#a78bfa"
        />
        <Metric
          label="Memory"
          current={memPct}
          series={points.map((p) => p.memPct)}
          stroke="#2dd4bf"
        />
      </div>
    </div>
  )
}

function Metric({
  label, current, series, stroke,
}: {
  label: string
  current: number | null
  series: (number | null)[]
  stroke: string
}) {
  const real = series.filter((v): v is number => v !== null)
  const avg = real.length ? real.reduce((a, b) => a + b, 0) / real.length : null
  const peak = real.length ? Math.max(...real) : null

  return (
    <div className="flex items-end justify-between gap-4">
      <div className="space-y-2">
        <div className="text-[10px] uppercase tracking-[0.18em] text-zinc-500 font-mono">
          {label}
        </div>
        <div className="flex items-baseline gap-1">
          <span className={`text-4xl font-medium tabular-nums tracking-tight font-sans ${tone(current)}`}>
            {current == null ? "—" : Math.round(current * 100)}
          </span>
          <span className="text-xs uppercase tracking-wider text-zinc-500 font-mono">%</span>
        </div>
        <div className="flex gap-3 text-[11px] font-mono text-zinc-500">
          <span>avg <span className="text-zinc-300 tabular-nums">{pct(avg)}</span></span>
          <span>peak <span className={`tabular-nums ${tone(peak)}`}>{pct(peak)}</span></span>
        </div>
      </div>
      <Sparkline values={series} stroke={stroke} width={180} height={44} domain={[0, 1]} />
    </div>
  )
}

function pct(v: number | null): string {
  return v == null ? "—" : `${Math.round(v * 100)}%`
}

// Same thresholds as the header SystemGauges.
function tone(v: number | null): string {
  if (v == null) return "text-zinc-500"
  if (v >= 0.95) return "text-red-400"
  if (v >= 0.8) return "text-amber-400"
  return "text-zinc-50"
}
