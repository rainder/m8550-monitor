import { formatBytes, formatRate } from "@/lib/format"
import type { Client } from "@/lib/types"

type Props = {
  clients: Client[]
  onClientClick?: (client: Client) => void
}

const BAND: Record<Client["connType"], { label: string; cls: string; mark: string }> = {
  host_2g: { label: "2.4 GHz", cls: "text-amber-300/80",  mark: "▪" },
  host_5g: { label: "5 GHz",   cls: "text-emerald-300/80", mark: "▪" },
  wired:   { label: "Wired",   cls: "text-zinc-400",       mark: "▪" },
}

export function ClientsTable({ clients, onClientClick }: Props) {
  if (clients.length === 0) {
    return (
      <Section title="Clients" count={0}>
        <div className="px-5 py-8 text-center text-xs text-zinc-500 font-mono">
          No clients connected
        </div>
      </Section>
    )
  }

  const sorted = [...clients].sort(
    (a, b) => (b.bandwidth ?? 0) - (a.bandwidth ?? 0),
  )
  const max = Math.max(1, ...sorted.map((c) => c.bandwidth ?? 0))

  return (
    <Section title="Clients" count={clients.length}>
      <div className="divide-y divide-[var(--color-border)]">
        {sorted.map((c) => {
          const band = BAND[c.connType]
          const pct = max > 0 ? Math.min(100, ((c.bandwidth ?? 0) / max) * 100) : 0
          const clickable = !!onClientClick
          return (
            <div
              key={c.mac}
              className={`grid grid-cols-[1fr_auto_auto_auto] gap-x-6 px-5 py-3 text-sm hover:bg-white/[0.02] transition-colors ${clickable ? "cursor-pointer" : ""}`}
              role={clickable ? "button" : undefined}
              tabIndex={clickable ? 0 : undefined}
              onClick={clickable ? () => onClientClick!(c) : undefined}
              onKeyDown={
                clickable
                  ? (e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault()
                        onClientClick!(c)
                      }
                    }
                  : undefined
              }
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className={`text-[8px] ${band.cls}`}>{band.mark}</span>
                  <span className="truncate text-zinc-100">{c.name ?? "Unknown"}</span>
                </div>
                <div className="mt-1 flex items-center gap-3 font-mono text-[11px] text-zinc-500">
                  <span>{c.ip ?? "—"}</span>
                  <span className="text-zinc-700">·</span>
                  <span className="hidden sm:inline">{c.mac}</span>
                </div>
              </div>

              <div className="hidden md:flex items-center text-[11px] uppercase tracking-wider font-mono text-zinc-500">
                {band.label}
              </div>

              <div className="hidden lg:flex items-center text-[11px] font-mono text-zinc-500 tabular-nums">
                {formatBytes(c.totalBytes)}
              </div>

              <div className="flex items-center gap-3 min-w-[140px] justify-end">
                <div className="hidden sm:block w-20 h-1 bg-white/[0.04] rounded-sm overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-emerald-500/40 to-emerald-400 transition-all duration-500"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="text-zinc-100 tabular-nums font-mono text-xs min-w-[80px] text-right">
                  {formatRate(c.bandwidth)}
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </Section>
  )
}

function Section({ title, count, children }: { title: string; count: number; children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
      <div className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-3">
        <h2 className="text-[10px] uppercase tracking-[0.18em] text-zinc-500 font-mono">
          {title}
        </h2>
        <span className="text-[11px] text-zinc-600 tabular-nums font-mono">
          {count} active
        </span>
      </div>
      {children}
    </div>
  )
}
