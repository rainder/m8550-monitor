import { describe, it, expect } from "vitest"

import { formatRate, splitRate } from "../lib/format"

describe("formatRate", () => {
  it("returns dash for null", () => {
    expect(formatRate(null)).toBe("—")
  })

  it("formats sub-1 MB/s with three decimals", () => {
    expect(formatRate(500)).toBe("0.001 MB/s")    // 0.0005 → rounds to 0.001
    expect(formatRate(15_000)).toBe("0.015 MB/s")
  })

  it("formats values >= 1 MB/s with two decimals", () => {
    expect(formatRate(1_500_000)).toBe("1.50 MB/s")
    expect(formatRate(123_456_789)).toBe("123.46 MB/s")
  })

  it("formats zero", () => {
    expect(formatRate(0)).toBe("0.00 MB/s")
  })
})

describe("splitRate", () => {
  it("splits null", () => {
    expect(splitRate(null)).toEqual(["—", ""])
  })

  it("splits sub-1 MB/s with three decimals", () => {
    expect(splitRate(15_000)).toEqual(["0.015", "MB/s"])
  })

  it("splits >= 1 MB/s with two decimals", () => {
    expect(splitRate(1_500_000)).toEqual(["1.50", "MB/s"])
  })

  it("splits zero", () => {
    expect(splitRate(0)).toEqual(["0.00", "MB/s"])
  })
})
