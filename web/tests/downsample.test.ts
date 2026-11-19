import { describe, it, expect } from "vitest"

import { alignClientSeries, downsample } from "../lib/downsample"
import type { HistoryPoint } from "../lib/types"

function point(
  ts: number, rxRate: number | null, txRate: number | null,
  cpuPct: number | null = null, memPct: number | null = null,
): HistoryPoint {
  return { ts, rxRate, txRate, cpuPct, memPct }
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

  it("averages cpu/mem fractions without integer rounding", () => {
    const points: HistoryPoint[] = [
      point(1, 0, 0, 0.1, 0.5),
      point(2, 0, 0, 0.2, null),
      point(3, 0, 0, null, null),
      point(4, 0, 0, null, null),
    ]
    const out = downsample(points, 2)
    expect(out[0].cpuPct).toBeCloseTo(0.15)
    expect(out[0].memPct).toBe(0.5)
    expect(out[1].cpuPct).toBeNull()
  })
})

describe("alignClientSeries", () => {
  it("aligns sparse per-mac rows onto a shared tick grid", () => {
    const rows = [
      { ts: 10, mac: "aa", name: "phone",    bandwidth: 100 },
      { ts: 10, mac: "bb", name: "laptop",   bandwidth: 200 },
      { ts: 20, mac: "aa", name: "phone",    bandwidth: 150 },
      // bb missing at 20
      { ts: 30, mac: "bb", name: "laptop",   bandwidth: 250 },
    ]
    const out = alignClientSeries(rows)

    expect(out.ticks).toEqual([10, 20, 30])
    expect(out.byMac["aa"]).toEqual([100, 150, null])
    expect(out.byMac["bb"]).toEqual([200, null, 250])
    // total: aa=250, bb=450 → bb first
    expect(out.meta.map((m) => m.mac)).toEqual(["bb", "aa"])
  })
})
