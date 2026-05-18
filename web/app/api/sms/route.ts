import { NextResponse } from "next/server"

import { listSms } from "@/lib/db"
import type { SmsResponse } from "@/lib/types"

export const dynamic = "force-dynamic"

export async function GET(): Promise<Response> {
  const { messages, syncedAt } = listSms()
  const body: SmsResponse = {
    unreadCount: messages.filter((m) => m.unread).length,
    messages,
    syncedAt,
  }
  return NextResponse.json(body)
}
