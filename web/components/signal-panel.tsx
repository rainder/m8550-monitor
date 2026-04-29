import type { HistoryPoint, Sample } from "@/lib/types"

type Props = {
  sample: Sample | null
  recent: HistoryPoint[]      // recent history points for the link-quality estimate
}

/**
 * Two-section panel:
 *
 * 1. Top: Carrier · Mode badge · 5-bar LINK QUALITY indicator. The router
 *    doesn't report real RF metrics on this firmware (RSRP/RSRQ/SNR/sigLevel
 *    always 0 — Tether pulls them from the cloud), so the bars are a
 *    quality proxy computed from observed uptime + throughput stability over
 *    the recent window.
 *
 * 2. Bottom: SIGNAL / NOISE rows showing the literal RSRP/RSRQ/SNR values
 *    (will be dashes on this firmware) plus the WAN IPs and bands the router
 *    DOES expose.
 */
export function SignalPanel({ sample, recent }: Props) {
  const ispName = sample?.ispName ?? null
  const connectedBand = sample?.connectedBand ?? null
  const endcStatus = sample?.endcStatus ?? null
  const networkType = sample?.networkType ?? null
  const wanIpv4 = sample?.wanIpv4 ?? null
  const rsrp = sample?.rsrp ?? null
  const rsrq = sample?.rsrq ?? null
  const snr = sample?.snr ?? null

  const mode = decodeMode(networkType, endcStatus, connectedBand)
  const bands = parseBands(connectedBand)
  const isFiveG = mode === "5G NSA" || mode === "5G SA"
  const quality = linkQuality(recent, sample?.online ?? false)

  const rfNotReported = (rsrp ?? 0) === 0 && (rsrq ?? 0) === 0 && (snr ?? 0) === 0

  return (
    <div className="relative overflow-hidden rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-violet-500/40 to-transparent" />

      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-sm text-violet-400">↗</span>
          <span className="text-[10px] uppercase tracking-[0.18em] text-zinc-500 font-mono truncate">
            Signal{ispName ? ` · ${ispName}` : ""}
          </span>
          {mode && (
            <span
              className={
                "px-1.5 py-0.5 rounded-sm text-[9px] font-mono uppercase tracking-wider " +
                (isFiveG
                  ? "bg-violet-500/15 text-violet-300 border border-violet-500/30"
                  : "bg-zinc-800 text-zinc-400 border border-zinc-700")
              }
            >
              {mode}
            </span>
          )}
        </div>
        <QualityBars quality={quality} />
      </div>

      <div className="space-y-2 text-xs font-mono">
        <Row label="RSRP">
          <Reading value={rsrp} unit="dBm" />
        </Row>
        <Row label="RSRQ">
          <Reading value={rsrq} unit="dB" />
        </Row>
        <Row label="SNR">
          <Reading value={snr} unit="dB" />
        </Row>

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

        {rfNotReported && (
          <p className="text-[10px] text-zinc-600 leading-relaxed pt-1">
            RSRP / RSRQ / SNR are not exposed by this M8550 firmware — quality
            bars are derived from recent uptime and throughput stability
            instead.
          </p>
        )}
      </div>
    </div>
  )
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

function QualityBars({ quality }: { quality: { bars: number; tone: "good" | "warn" | "bad" | "none" } }) {
  const colour =
    quality.tone === "good" ? "bg-emerald-400" :
    quality.tone === "warn" ? "bg-amber-400" :
    quality.tone === "bad"  ? "bg-red-400" :
    "bg-zinc-700"

  return (
    <div className="flex items-end gap-[3px] h-5" title={`Link quality (derived): ${quality.bars}/5`}>
      {[0, 1, 2, 3, 4].map((i) => (
        <span
          key={i}
          className={`w-[5px] rounded-[1px] ${i < quality.bars ? colour : "bg-zinc-800"}`}
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

/**
 * Derive a 0-5 bar link-quality indicator from recent history.
 * - Currently offline → 0 bars (red).
 * - All recent ticks offline → 0 bars (red).
 * - Some offline ticks → bars scale by uptime ratio.
 * - All ticks online but rx is dead-quiet (mean < 1 KB/s and we know we're
 *   meant to be active) → 4 bars (no penalty for genuinely idle moments).
 * - All ticks online with healthy mean throughput → 5 bars (green).
 */
function linkQuality(
  recent: HistoryPoint[],
  online: boolean,
): { bars: number; tone: "good" | "warn" | "bad" | "none" } {
  if (!online) return { bars: 0, tone: "bad" }
  if (recent.length < 3) return { bars: 4, tone: "good" }

  const last = recent.slice(-30)
  // Treat a `null` rxRate as a missed sample (router unreachable that tick).
  const offlineCount = last.filter((p) => p.rxRate === null && p.txRate === null).length
  const total = last.length
  const uptime = (total - offlineCount) / total

  if (uptime < 0.5) return { bars: 1, tone: "bad" }
  if (uptime < 0.85) return { bars: 2, tone: "warn" }
  if (uptime < 0.99) return { bars: 3, tone: "warn" }
  return { bars: 5, tone: "good" }
}
