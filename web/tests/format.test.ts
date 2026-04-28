import { describe, it, expect } from "vitest"

import { formatRate } from "../lib/format"

describe("formatRate", () => {
  it("returns dash for null", () => {
    expect(formatRate(null)).toBe("—")
  })

  it("formats below 1 KB/s in B/s", () => {
    expect(formatRate(500)).toBe("500 B/s")
  })

  it("formats KB/s with one decimal", () => {
    expect(formatRate(1500)).toBe("1.5 KB/s")
  })

  it("formats MB/s with two decimals", () => {
    expect(formatRate(1_500_000)).toBe("1.50 MB/s")
  })

  it("formats GB/s with two decimals", () => {
    expect(formatRate(1_500_000_000)).toBe("1.50 GB/s")
  })

  it("formats zero", () => {
    expect(formatRate(0)).toBe("0 B/s")
  })
})
