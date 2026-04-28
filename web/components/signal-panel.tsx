import type { Sample } from "@/lib/types"

type Props = {
  sample: Sample | null
}

export function SignalPanel({ sample }: Props) {
  const sigLevel = sample?.sigLevel ?? null
  const ispName = sample?.ispName ?? null
  const rsrp = sample?.rsrp ?? null
  const rsrq = sample?.rsrq ?? null
  const snr = sample?.snr ?? null

  // 5 bars, fill from left.
  const filled = Math.max(0, Math.min(5, sigLevel ?? 0))
  // Colour the filled bars by quality: 4-5 green, 2-3 amber, 0-1 red.
  const fillColour =
    sigLevel == null ? "bg-zinc-700" :
    sigLevel >= 4 ? "bg-emerald-400" :
    sigLevel >= 2 ? "bg-amber-400" :
    "bg-red-400"

  return (
    <div className="relative overflow-hidden rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
      {/* hairline accent at top — purple/violet for the signal card to differentiate it */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-violet-500/40 to-transparent" />

      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2">
          <span className="text-sm text-violet-400">↗</span>
          <span className="text-[10px] uppercase tracking-[0.18em] text-zinc-500 font-mono">
            Signal{ispName ? ` · ${ispName}` : ""}
          </span>
        </div>
        {/* 5 bars, increasing height from left to right. */}
        <div className="flex items-end gap-[3px] h-5">
          {[0, 1, 2, 3, 4].map((i) => (
            <span
              key={i}
              className={`w-[5px] rounded-[1px] ${i < filled ? fillColour : "bg-zinc-800"}`}
              style={{ height: `${30 + i * 14}%` }}
            />
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-y-2 gap-x-6 text-xs font-mono">
        <Field label="RSRP" value={rsrp} unit="dBm" />
        <Field label="RSRQ" value={rsrq} unit="dB" />
        <Field label="SNR"  value={snr}  unit="dB" />
      </div>
    </div>
  )
}

function Field({ label, value, unit }: { label: string; value: number | null; unit: string }) {
  return (
    <div className="flex items-baseline justify-between">
      <span className="uppercase tracking-wider text-zinc-500">{label}</span>
      <span>
        <span className="text-zinc-100 tabular-nums">{value ?? "—"}</span>
        <span className="text-zinc-600 ml-1">{unit}</span>
      </span>
    </div>
  )
}
