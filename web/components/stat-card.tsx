import { splitRate } from "@/lib/format"
import { Sparkline } from "./sparkline"

type Props = {
  label: string
  rate: number | null
  sparkValues: (number | null)[]
  accent: "down" | "up"
}

const ACCENT = {
  down: { stroke: "#4ade80", text: "text-green-400", arrow: "↓" },
  up:   { stroke: "#60a5fa", text: "text-blue-400",  arrow: "↑" },
} as const

export function StatCard({ label, rate, sparkValues, accent }: Props) {
  const a = ACCENT[accent]
  const [num, unit] = splitRate(rate)

  return (
    <div className="relative overflow-hidden rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
      {/* hairline accent at top */}
      <div className={`absolute inset-x-0 top-0 h-px ${accent === "down" ? "bg-gradient-to-r from-transparent via-green-500/40 to-transparent" : "bg-gradient-to-r from-transparent via-blue-500/40 to-transparent"}`} />

      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className={`text-sm ${a.text}`}>{a.arrow}</span>
          <span className="text-[10px] uppercase tracking-[0.18em] text-zinc-500 font-mono">
            {label}
          </span>
        </div>
        <Sparkline values={sparkValues} stroke={a.stroke} width={88} height={24} />
      </div>

      <div className="flex items-baseline gap-2">
        <span className="text-4xl font-medium tabular-nums tracking-tight text-zinc-50 font-sans">
          {num}
        </span>
        <span className="text-xs uppercase tracking-wider text-zinc-500 font-mono">
          {unit}
        </span>
      </div>
    </div>
  )
}
