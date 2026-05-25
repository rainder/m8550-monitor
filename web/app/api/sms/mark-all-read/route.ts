import { NextResponse } from "next/server"

import { enqueueSmsAction } from "@/lib/sms-db"

export const dynamic = "force-dynamic"

export async function POST(): Promise<Response> {
  // sms_id is unused for the inbox-wide action — pass 0 as a sentinel so
  // the not-null column stays happy.
  enqueueSmsAction(0, "mark_all_read")
  return NextResponse.json({ ok: true })
}
