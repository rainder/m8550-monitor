type Props = {
  cpuPct: number | null
  memPct: number | null
}

export function SystemGauges({ cpuPct, memPct }: Props) {
  return (
    <div className="hidden lg:flex items-center gap-5">
      <Gauge label="CPU" pct={cpuPct} />
      <Gauge label="MEM" pct={memPct} />
    </div>
  )
}

function Gauge({ label, pct }: { label: string; pct: number | null }) {
  const cells = 6
  const filled = pct == null ? 0 : Math.round(pct * cells)
  const colour =
    pct == null ? "bg-zinc-700" :
    pct >= 0.95 ? "bg-red-400" :
    pct >= 0.8  ? "bg-amber-400" :
    "bg-zinc-300"

  return (
    <div className="flex items-center gap-2 text-[11px] font-mono">
      <span className="uppercase tracking-wider text-zinc-600">{label}</span>
      <div className="flex items-center gap-[2px]">
        {Array.from({ length: cells }).map((_, i) => (
          <span
            key={i}
            className={`block h-3 w-[3px] rounded-[1px] ${i < filled ? colour : "bg-zinc-800"}`}
          />
        ))}
      </div>
      <span className="text-zinc-300 tabular-nums w-[28px] text-right">
        {pct == null ? "—" : `${Math.round(pct * 100)}%`}
      </span>
    </div>
  )
}
