import { describe, it, expect } from "vitest"

import { downsample } from "../lib/downsample"
import type { HistoryPoint } from "../lib/types"

function point(ts: number, rxRate: number | null, txRate: number | null): HistoryPoint {
  return { ts, rxRate, txRate }
}

describe("downsample", () => {
  it("returns input when fewer points than target", () => {
    const points = [point(1, 10, 5), point(2, 20, 10), point(3, 30, 15)]
    expect(downsample(points, 10)).toEqual(points)
  })

  it("buckets and averages when over target", () => {
    const points: HistoryPoint[] = []
    for (let i = 0; i < 100; i++) points.push(point(i, i, i * 2))
    const out = downsample(points, 10)
    expect(out).toHaveLength(10)
    expect(out[0].ts).toBe(0)
    expect(out[9].ts).toBeGreaterThanOrEqual(90)
  })

  it("preserves nulls (no average through null)", () => {
    const points: HistoryPoint[] = [
      point(1, 10, 10),
      point(2, null, null),
      point(3, 30, 30),
      point(4, 40, 40),
    ]
    const out = downsample(points, 2)
    // bucket1=[1,2] → avg of [10] = 10; bucket2=[3,4] → avg of [30,40] = 35
    expect(out[0].rxRate).toBe(10)
    expect(out[1].rxRate).toBe(35)
  })

  it("emits null when all points in bucket are null", () => {
    const points: HistoryPoint[] = [
      point(1, null, null),
      point(2, null, null),
      point(3, 30, 30),
      point(4, 40, 40),
    ]
    const out = downsample(points, 2)
    expect(out[0].rxRate).toBeNull()
    expect(out[1].rxRate).toBe(35)
  })
})
