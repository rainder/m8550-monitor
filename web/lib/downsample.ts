import type { HistoryPoint } from "./types"

export function downsample(points: HistoryPoint[], target: number): HistoryPoint[] {
  if (points.length <= target) return points
  const bucketSize = Math.ceil(points.length / target)
  const out: HistoryPoint[] = []
  for (let i = 0; i < points.length; i += bucketSize) {
    const bucket = points.slice(i, i + bucketSize)
    out.push({
      ts: bucket[0].ts,
      rxRate: avg(bucket.map((p) => p.rxRate)),
      txRate: avg(bucket.map((p) => p.txRate)),
    })
  }
  return out
}

function avg(values: (number | null)[]): number | null {
  const real = values.filter((v): v is number => v !== null)
  if (real.length === 0) return null
  return Math.round(real.reduce((a, b) => a + b, 0) / real.length)
}

export interface AlignedSeries {
  ticks: number[]
  /** For each mac key, an array of values aligned to ticks (null = no data at that tick). */
  byMac: Record<string, (number | null)[]>
  /** Display-order mac keys, with names attached. */
  meta: { mac: string; name: string | null }[]
}

interface RawClientRow {
  ts: number
  mac: string
  name: string | null
  bandwidth: number | null
}

/**
 * Build aligned per-client series from raw rows. Rows must be sorted by ts asc.
 * - Ticks are the unique sorted ts values.
 * - Per mac, each tick has the row's bandwidth value or null if absent.
 * - meta is sorted by total bandwidth across the window (busiest first).
 */
export function alignClientSeries(rows: RawClientRow[]): AlignedSeries {
  const tickSet = new Set<number>()
  const macs = new Map<string, string | null>()
  for (const r of rows) {
    tickSet.add(r.ts)
    if (!macs.has(r.mac)) macs.set(r.mac, r.name)
    else if (r.name && !macs.get(r.mac)) macs.set(r.mac, r.name)
  }
  const ticks = [...tickSet].sort((a, b) => a - b)
  const tickIndex = new Map(ticks.map((t, i) => [t, i]))

  const byMac: Record<string, (number | null)[]> = {}
  for (const mac of macs.keys()) {
    byMac[mac] = new Array(ticks.length).fill(null)
  }
  for (const r of rows) {
    byMac[r.mac][tickIndex.get(r.ts)!] = r.bandwidth
  }

  // Sort macs by total bandwidth across the window, descending. Stable; keeps
  // the legend ordered busiest-first. Ties broken by mac for determinism.
  const totals = new Map<string, number>()
  for (const mac of macs.keys()) {
    totals.set(mac, byMac[mac].reduce((a: number, v) => a + (v ?? 0), 0))
  }
  const meta = [...macs.entries()]
    .map(([mac, name]) => ({ mac, name }))
    .sort((a, b) => {
      const t = (totals.get(b.mac) ?? 0) - (totals.get(a.mac) ?? 0)
      return t !== 0 ? t : a.mac.localeCompare(b.mac)
    })

  return { ticks, byMac, meta }
}

/**
 * Bucket-downsample an AlignedSeries to ~target ticks. Each bucket's value
 * per mac is the average of non-null values in that bucket; if all null,
 * the bucket is null. Ticks become the first ts of each bucket (matches the
 * existing wan downsample).
 */
export function downsampleAligned(input: AlignedSeries, target: number): AlignedSeries {
  if (input.ticks.length <= target) return input
  const bucketSize = Math.ceil(input.ticks.length / target)

  const newTicks: number[] = []
  const newByMac: Record<string, (number | null)[]> = {}
  for (const mac of Object.keys(input.byMac)) newByMac[mac] = []

  for (let i = 0; i < input.ticks.length; i += bucketSize) {
    newTicks.push(input.ticks[i])
    for (const mac of Object.keys(input.byMac)) {
      const slice = input.byMac[mac].slice(i, i + bucketSize)
      const real = slice.filter((v): v is number => v !== null)
      newByMac[mac].push(real.length === 0 ? null : Math.round(real.reduce((a, b) => a + b, 0) / real.length))
    }
  }

  return { ticks: newTicks, byMac: newByMac, meta: input.meta }
}
