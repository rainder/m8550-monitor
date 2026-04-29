import type { Sample } from "@/lib/types"

type Props = {
  sample: Sample | null
}

/**
 * Two-section panel:
 *
 * 1. Top: Carrier · Mode badge · 5-bar signal-strength indicator.
 *    Primary radio is 5G NR when ssRsrp is available, otherwise LTE.
 *    Bars reflect the primary cell's signalStrength (0..5 from firmware).
 *    Colour is based on RSRP / SS-RSRP thresholds.
 *
 * 2. Bottom: RSRP / RSRQ / SINR|SNR rows (real values from
 *    DEV2_LTE_SERVING_CELL_INFO) plus BANDS chips and WAN IP.
 */
export function SignalPanel({ sample }: Props) {
  const ispName       = sample?.ispName       ?? null
  const connectedBand = sample?.connectedBand ?? null
  const endcStatus    = sample?.endcStatus    ?? null
  const networkType   = sample?.networkType   ?? null
  const wanIpv4       = sample?.wanIpv4       ?? null

  // LTE cell
  const rsrp             = sample?.rsrp             ?? null
  const rsrq             = sample?.rsrq             ?? null
  const snr              = sample?.snr              ?? null
  const lteSignalStrength = sample?.lteSignalStrength ?? null

  // NR cell
  const ssRsrp            = sample?.ssRsrp            ?? null
  const ssRsrq            = sample?.ssRsrq            ?? null
  const ssSinr            = sample?.ssSinr            ?? null
  const nrSignalStrength  = sample?.nrSignalStrength  ?? null

  // Prefer NR when ssRsrp is present and non-zero
  const hasNr  = ssRsrp !== null && ssRsrp !== 0
  const hasLte = rsrp   !== null && rsrp   !== 0

  const primary: "nr" | "lte" | "none" = hasNr ? "nr" : hasLte ? "lte" : "none"

  const bars = primary === "nr"
    ? (nrSignalStrength ?? 0)
    : primary === "lte"
      ? (lteSignalStrength ?? 0)
      : 0

  const tone = primary === "nr"
    ? nrTone(ssRsrp!)
    : primary === "lte"
      ? lteTone(rsrp!)
      : "none"

  const mode = decodeMode(networkType, endcStatus, connectedBand)
  const bands = parseBands(connectedBand)
  const isFiveG = primary === "nr" || mode === "5G NSA" || mode === "5G SA"

  return (
    <div className="relative overflow-hidden rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-violet-500/40 to-transparent" />

      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-sm text-violet-400">↗</span>
          <span className="text-[10px] uppercase tracking-[0.18em] text-zinc-500 font-mono truncate">
            Signal{ispName ? ` · ${ispName}` : ""}
          </span>
          {primary !== "none" && (
            <span
              className={
                "px-1.5 py-0.5 rounded-sm text-[9px] font-mono uppercase tracking-wider " +
                (isFiveG
                  ? "bg-violet-500/15 text-violet-300 border border-violet-500/30"
                  : "bg-zinc-800 text-zinc-400 border border-zinc-700")
              }
            >
              {primary === "nr" ? "5G NR" : "LTE"}
            </span>
          )}
          {primary === "none" && mode && (
            <span className="px-1.5 py-0.5 rounded-sm text-[9px] font-mono uppercase tracking-wider bg-zinc-800 text-zinc-400 border border-zinc-700">
              {mode}
            </span>
          )}
        </div>
        <SignalBars bars={bars} tone={tone} primary={primary} />
      </div>

      <div className="space-y-2 text-xs font-mono">
        {primary === "nr" ? (
          <>
            <Row label="RSRP">
              <Reading value={ssRsrp} unit="dBm" />
            </Row>
            <Row label="RSRQ">
              <Reading value={ssRsrq} unit="dB" />
            </Row>
            <Row label="SINR">
              <ReadingScaled value={ssSinr} unit="dB" />
            </Row>
          </>
        ) : (
          <>
            <Row label="RSRP">
              <Reading value={rsrp} unit="dBm" />
            </Row>
            <Row label="RSRQ">
              <Reading value={rsrq} unit="dB" />
            </Row>
            <Row label="SNR">
              <ReadingScaled value={snr} unit="dB" />
            </Row>
          </>
        )}

        <div className="my-2 border-t border-[var(--color-border)]" />

        <Row label="Bands">
          {bands.length === 0 ? (
            <span className="text-zinc-600">—</span>
          ) : (
            <span className="flex items-center gap-1.5">
              {bands.map((b) => <BandChip key={b.label} band={b} />)}
            </span>
          )}
        </Row>
        <Row label="WAN">
          <span className={wanIpv4 ? "text-zinc-300 tabular-nums" : "text-zinc-600"}>
            {wanIpv4 ?? "—"}
          </span>
        </Row>
      </div>
    </div>
  )
}

function nrTone(rsrp: number): "good" | "warn" | "bad" {
  if (rsrp >= -80) return "good"
  if (rsrp >= -100) return "warn"
  return "bad"
}

function lteTone(rsrp: number): "good" | "warn" | "bad" {
  if (rsrp >= -90) return "good"
  if (rsrp >= -110) return "warn"
  return "bad"
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="uppercase tracking-wider text-zinc-500 shrink-0">{label}</span>
      <span className="text-right min-w-0">{children}</span>
    </div>
  )
}

function Reading({ value, unit }: { value: number | null; unit: string }) {
  const real = value !== null && value !== 0
  return (
    <span>
      <span className={real ? "text-zinc-100 tabular-nums" : "text-zinc-600 tabular-nums"}>
        {real ? value : "—"}
      </span>
      <span className="text-zinc-700 ml-1">{unit}</span>
    </span>
  )
}

/** For ×10-scaled fields (SNR, SINR): displays value/10 to one decimal place. */
function ReadingScaled({ value, unit }: { value: number | null; unit: string }) {
  const real = value !== null && value !== 0
  return (
    <span>
      <span className={real ? "text-zinc-100 tabular-nums" : "text-zinc-600 tabular-nums"}>
        {real ? (value! / 10).toFixed(1) : "—"}
      </span>
      <span className="text-zinc-700 ml-1">{unit}</span>
    </span>
  )
}

function SignalBars({
  bars,
  tone,
  primary,
}: {
  bars: number
  tone: "good" | "warn" | "bad" | "none"
  primary: "nr" | "lte" | "none"
}) {
  const colour =
    tone === "good" ? "bg-emerald-400" :
    tone === "warn" ? "bg-amber-400" :
    tone === "bad"  ? "bg-red-400" :
    "bg-zinc-700"

  const label = primary === "none"
    ? "No signal data"
    : `Signal strength: ${bars}/5`

  return (
    <div className="flex items-end gap-[3px] h-5" title={label}>
      {[0, 1, 2, 3, 4].map((i) => (
        <span
          key={i}
          className={`w-[5px] rounded-[1px] ${i < bars ? colour : "bg-zinc-800"}`}
          style={{ height: `${30 + i * 14}%` }}
        />
      ))}
    </div>
  )
}

type Band = { label: string; tone: "lte" | "nr" }

function BandChip({ band }: { band: Band }) {
  const cls =
    band.tone === "nr"
      ? "bg-violet-500/15 text-violet-200 border-violet-500/30"
      : "bg-zinc-800 text-zinc-300 border-zinc-700"
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded-sm text-[10px] border ${cls}`}>
      {band.label}
    </span>
  )
}

function parseBands(s: string | null): Band[] {
  if (!s) return []
  return s
    .split(/[;,\s]+/)
    .map((p) => p.trim())
    .filter(Boolean)
    .map((label) => ({
      label,
      tone: label.toUpperCase().startsWith("N") ? "nr" : "lte",
    }))
}

function decodeMode(
  networkType: number | null,
  endcStatus: number | null,
  connectedBand: string | null,
): string | null {
  if (endcStatus === 1) return "5G NSA"
  const hasNr  = !!connectedBand && /\bN\d+/i.test(connectedBand)
  const hasLte = !!connectedBand && /\bB\d+/i.test(connectedBand)
  if (hasNr && hasLte) return "5G NSA"
  if (hasNr) return "5G SA"
  if (hasLte) return "LTE"
  if (networkType === null) return null
  return `Type ${networkType}`
}
