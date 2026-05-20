import { NextResponse } from "next/server"

import { enqueueSmsAction } from "@/lib/sms-db"

export const dynamic = "force-dynamic"

export async function POST(
  _req: Request,
  ctx: { params: Promise<{ id: string }> },
): Promise<Response> {
  const { id } = await ctx.params
  const smsId = Number.parseInt(id, 10)
  if (!Number.isFinite(smsId) || smsId <= 0) {
    return NextResponse.json({ error: "invalid id" }, { status: 400 })
  }
  enqueueSmsAction(smsId, "mark_read")
  return NextResponse.json({ ok: true })
}
