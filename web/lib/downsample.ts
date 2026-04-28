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
