import { NextResponse } from "next/server"

import { samplesSince } from "@/lib/db"
import { downsample } from "@/lib/downsample"
import type { HistoryRange, HistoryResponse } from "@/lib/types"

export const dynamic = "force-dynamic"

const RANGE_SECONDS: Record<HistoryRange, number> = {
  "1h": 60 * 60,
  "24h": 24 * 60 * 60,
  "7d": 7 * 24 * 60 * 60,
}

const TARGET_POINTS = 500

export async function GET(req: Request): Promise<Response> {
  const url = new URL(req.url)
  const rangeParam = url.searchParams.get("range") ?? "1h"
  if (!(rangeParam in RANGE_SECONDS)) {
    return NextResponse.json({ error: "invalid range" }, { status: 400 })
  }
  const range = rangeParam as HistoryRange
  const sinceTs = Math.floor(Date.now() / 1000) - RANGE_SECONDS[range]
  const raw = samplesSince(sinceTs)
  const points = downsample(raw, TARGET_POINTS)
  const body: HistoryResponse = { range, points }
  return NextResponse.json(body)
}
