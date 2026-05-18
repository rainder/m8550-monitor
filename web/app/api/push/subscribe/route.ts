import { NextResponse } from "next/server"

import { addSubscription, deleteSubscription } from "@/lib/push-db"

export const dynamic = "force-dynamic"

interface SubscribePayload {
  endpoint?: unknown
  keys?: { p256dh?: unknown; auth?: unknown }
}

export async function POST(req: Request): Promise<Response> {
  let body: SubscribePayload
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 })
  }
  const endpoint = typeof body.endpoint === "string" ? body.endpoint : null
  const p256dh = typeof body.keys?.p256dh === "string" ? body.keys.p256dh : null
  const auth = typeof body.keys?.auth === "string" ? body.keys.auth : null
  if (!endpoint || !p256dh || !auth) {
    return NextResponse.json(
      { error: "endpoint, keys.p256dh, keys.auth required" },
      { status: 400 },
    )
  }
  addSubscription(endpoint, p256dh, auth)
  return NextResponse.json({ ok: true })
}

export async function DELETE(req: Request): Promise<Response> {
  let body: { endpoint?: unknown }
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 })
  }
  const endpoint = typeof body.endpoint === "string" ? body.endpoint : null
  if (!endpoint) {
    return NextResponse.json({ error: "endpoint required" }, { status: 400 })
  }
  deleteSubscription(endpoint)
  return NextResponse.json({ ok: true })
}
