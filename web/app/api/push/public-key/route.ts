import { NextResponse } from "next/server"

import { readVapidPublicKey } from "@/lib/push-db"

export const dynamic = "force-dynamic"

export async function GET(): Promise<Response> {
  const publicKey = readVapidPublicKey()
  if (!publicKey) {
    return NextResponse.json(
      { error: "VAPID keys not ready yet — check collector logs" },
      { status: 503 },
    )
  }
  return NextResponse.json({ publicKey })
}
