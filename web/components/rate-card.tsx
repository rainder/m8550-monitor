import { formatRate } from "@/lib/format"

type Props = {
  label: string
  rate: number | null
  arrow: "↓" | "↑"
}

export function RateCard({ label, rate, arrow }: Props) {
  return (
    <div className="bg-zinc-900 rounded-lg p-5 border border-zinc-800">
      <div className="text-xs uppercase tracking-wider text-zinc-500 mb-2">
        {arrow} {label}
      </div>
      <div className="text-3xl font-semibold tabular-nums">
        {formatRate(rate)}
      </div>
    </div>
  )
}
