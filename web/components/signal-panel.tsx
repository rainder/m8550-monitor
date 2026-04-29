import type { Sample } from "@/lib/types"

type Props = {
  sample: Sample | null
}

/**
 * The M8550 firmware exposes link / band / IP information locally, but does
 * NOT report live signal numbers (RSRP / RSRQ / SNR / sigLevel always 0 — the
 * Tether app gets those from the cloud API). This panel surfaces the bits the
 * router will actually tell us: carrier, mode (5G NSA / LTE), connected
 * bands, and WAN IPs.
 */
export function SignalPanel({ sample }: Props) {
  const ispName = sample?.ispName ?? null
  const connectedBand = sample?.connectedBand ?? null
  const endcStatus = sample?.endcStatus ?? null
  const networkType = sample?.networkType ?? null
  const wanIpv4 = sample?.wanIpv4 ?? null
  const wanIpv6 = sample?.wanIpv6 ?? null

  const mode = decodeMode(networkType, endcStatus, connectedBand)
  const bands = parseBands(connectedBand)
  const isFiveG = mode === "5G NSA" || mode === "5G SA"

  return (
    <div className="relative overflow-hidden rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-violet-500/40 to-transparent" />

      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2">
          <span className="text-sm text-violet-400">↗</span>
          <span className="text-[10px] uppercase tracking-[0.18em] text-zinc-500 font-mono">
            Network{ispName ? ` · ${ispName}` : ""}
          </span>
        </div>
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

      <div className="space-y-2 text-xs font-mono">
        <Row label="Bands">
          {bands.length === 0 ? (
            <span className="text-zinc-600">—</span>
          ) : (
            <span className="flex items-center gap-1.5">
              {bands.map((b) => (
                <BandChip key={b.label} band={b} />
              ))}
            </span>
          )}
        </Row>

        <Row label="WAN v4">
          <span className={wanIpv4 ? "text-zinc-100 tabular-nums" : "text-zinc-600"}>
            {wanIpv4 ?? "—"}
          </span>
        </Row>

        <Row label="WAN v6">
          <span
            className={wanIpv6 ? "text-zinc-300 tabular-nums truncate max-w-[220px]" : "text-zinc-600"}
            title={wanIpv6 ?? undefined}
          >
            {wanIpv6 ?? "—"}
          </span>
        </Row>
      </div>
    </div>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="uppercase tracking-wider text-zinc-500 shrink-0">{label}</span>
      <span className="text-right">{children}</span>
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
  // Format observed: "B3;N40" — semicolon-separated. LTE bands start with B,
  // NR bands start with N. Be lenient with separators.
  return s
    .split(/[;,\s]+/)
    .map((part) => part.trim())
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
  // M8550 firmware codes (verified empirically):
  //   8 → 5G NSA (anchor LTE + secondary NR), confirmed by endcStatus=1.
  // We fall back to inspecting band names if networkType is missing/unknown.
  if (endcStatus === 1) return "5G NSA"
  const hasNr = !!connectedBand && /\bN\d+/i.test(connectedBand)
  const hasLte = !!connectedBand && /\bB\d+/i.test(connectedBand)
  if (hasNr && hasLte) return "5G NSA"
  if (hasNr) return "5G SA"
  if (hasLte) return "LTE"
  if (networkType === null) return null
  return `Type ${networkType}`
}
