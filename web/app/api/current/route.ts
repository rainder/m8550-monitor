import { NextResponse } from "next/server"

import { clientsAt, latestSample } from "@/lib/db"
import type { CurrentResponse } from "@/lib/types"

export const dynamic = "force-dynamic"

export async function GET(): Promise<Response> {
  const sample = latestSample()
  if (!sample) {
    const body: CurrentResponse = { sample: null, clients: [], ageSeconds: 0 }
    return NextResponse.json(body)
  }
  const clients = clientsAt(sample.ts)
  const ageSeconds = Math.max(0, Math.floor(Date.now() / 1000) - sample.ts)
  const body: CurrentResponse = { sample, clients, ageSeconds }
  return NextResponse.json(body)
}
