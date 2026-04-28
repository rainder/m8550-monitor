import { formatRate } from "@/lib/format"
import type { Client } from "@/lib/types"

type Props = { clients: Client[] }

const BAND_LABEL: Record<Client["connType"], string> = {
  host_2g: "2.4G",
  host_5g: "5G",
  wired: "Wired",
}

const BAND_COLOUR: Record<Client["connType"], string> = {
  host_2g: "text-amber-400",
  host_5g: "text-green-400",
  wired: "text-zinc-400",
}

export function ClientsTable({ clients }: Props) {
  if (clients.length === 0) {
    return (
      <div className="bg-zinc-900 rounded-lg p-5 border border-zinc-800 text-zinc-500 text-sm">
        No clients connected.
      </div>
    )
  }

  const sorted = [...clients].sort(
    (a, b) => (b.bandwidth ?? 0) - (a.bandwidth ?? 0),
  )

  return (
    <div className="bg-zinc-900 rounded-lg border border-zinc-800 overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-zinc-800/50 text-zinc-400 text-xs uppercase">
          <tr>
            <th className="text-left px-4 py-2">Name</th>
            <th className="text-left px-4 py-2">IP</th>
            <th className="text-left px-4 py-2 hidden sm:table-cell">MAC</th>
            <th className="text-left px-4 py-2">Band</th>
            <th className="text-right px-4 py-2">↕ Bandwidth</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-800">
          {sorted.map((c) => (
            <tr key={c.mac}>
              <td className="px-4 py-2">{c.name ?? "—"}</td>
              <td className="px-4 py-2 font-mono text-xs">{c.ip ?? "—"}</td>
              <td className="px-4 py-2 font-mono text-xs hidden sm:table-cell">{c.mac}</td>
              <td className={`px-4 py-2 text-xs font-medium ${BAND_COLOUR[c.connType]}`}>
                {BAND_LABEL[c.connType]}
              </td>
              <td className="px-4 py-2 text-right tabular-nums">{formatRate(c.bandwidth)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
