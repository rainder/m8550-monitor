import { NextResponse } from "next/server"

import { enqueueRouterAction } from "@/lib/sms-db"

export const dynamic = "force-dynamic"

export async function POST(): Promise<Response> {
  enqueueRouterAction("reauth")
  return NextResponse.json({ ok: true })
}
