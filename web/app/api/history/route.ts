import { NextResponse } from "next/server"

import { clientHistorySince, samplesSince } from "@/lib/db"
import { alignClientSeries, downsample, downsampleAligned } from "@/lib/downsample"
import type {
  ClientHistoryResponse, HistoryMode, HistoryRange, HistoryResponse,
} from "@/lib/types"

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
  const modeParam: HistoryMode = (url.searchParams.get("mode") as HistoryMode) ?? "wan"
  if (!(rangeParam in RANGE_SECONDS)) {
    return NextResponse.json({ error: "invalid range" }, { status: 400 })
  }
  if (modeParam !== "wan" && modeParam !== "clients") {
    return NextResponse.json({ error: "invalid mode" }, { status: 400 })
  }
  const range = rangeParam as HistoryRange
  const sinceTs = Math.floor(Date.now() / 1000) - RANGE_SECONDS[range]

  if (modeParam === "wan") {
    const raw = samplesSince(sinceTs)
    const points = downsample(raw, TARGET_POINTS)
    const body: HistoryResponse = { range, points }
    return NextResponse.json(body)
  }

  // mode === "clients"
  const aligned = alignClientSeries(clientHistorySince(sinceTs))
  const ds = downsampleAligned(aligned, TARGET_POINTS)
  const body: ClientHistoryResponse = {
    range,
    mode: "clients",
    ticks: ds.ticks,
    series: ds.meta.map((m) => ({
      mac: m.mac,
      name: m.name,
      values: ds.byMac[m.mac] ?? [],
    })),
  }
  return NextResponse.json(body)
}
