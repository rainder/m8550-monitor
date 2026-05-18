"use client"

import { useEffect, useState } from "react"

type State =
  | { kind: "unsupported" }
  | { kind: "denied" }
  | { kind: "off" }
  | { kind: "on" }
  | { kind: "working" }
  | { kind: "error"; message: string }

export function NotificationsToggle() {
  const [state, setState] = useState<State>({ kind: "working" })

  useEffect(() => {
    void detectInitialState().then(setState)
  }, [])

  async function enable() {
    setState({ kind: "working" })
    try {
      const next = await subscribe()
      setState(next)
    } catch (e) {
      setState({ kind: "error", message: messageOf(e) })
    }
  }

  async function disable() {
    setState({ kind: "working" })
    try {
      await unsubscribe()
      setState({ kind: "off" })
    } catch (e) {
      setState({ kind: "error", message: messageOf(e) })
    }
  }

  if (state.kind === "unsupported") {
    return (
      <div className="hidden md:flex items-center gap-2 text-[11px] font-mono text-zinc-600">
        <span className="uppercase tracking-wider">Push</span>
        <span>n/a here</span>
      </div>
    )
  }

  if (state.kind === "denied") {
    return (
      <div
        className="hidden md:flex items-center gap-2 text-[11px] font-mono text-zinc-500"
        title="Notifications are blocked at the browser/OS level. Re-enable them in your device settings to use this."
      >
        <span className="uppercase tracking-wider">Push</span>
        <span className="text-amber-400">blocked</span>
      </div>
    )
  }

  const label = state.kind === "on" ? "on" : state.kind === "working" ? "…" : "off"
  const action = state.kind === "on" ? disable : enable
  const disabled = state.kind === "working"

  return (
    <div className="flex items-center gap-2 text-[11px] font-mono">
      <span className="hidden md:inline uppercase tracking-wider text-zinc-600">Push</span>
      <button
        type="button"
        onClick={action}
        disabled={disabled}
        className={
          "rounded-sm border px-2 py-0.5 tabular-nums transition-colors " +
          "disabled:opacity-60 disabled:cursor-not-allowed " +
          (state.kind === "on"
            ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20"
            : "border-[var(--color-border)] text-zinc-400 hover:text-zinc-200 hover:border-zinc-500")
        }
        title={
          state.kind === "error" ? state.message
            : state.kind === "on" ? "Notifications on for this device. Click to turn off."
            : "Send SMS alerts to this device."
        }
      >
        {label}
      </button>
    </div>
  )
}

async function detectInitialState(): Promise<State> {
  if (
    typeof window === "undefined" ||
    !("serviceWorker" in navigator) ||
    !("PushManager" in window) ||
    !("Notification" in window)
  ) {
    return { kind: "unsupported" }
  }
  if (Notification.permission === "denied") return { kind: "denied" }
  // If we already have a subscription on this device, treat as on.
  try {
    const reg = await navigator.serviceWorker.getRegistration()
    if (reg) {
      const sub = await reg.pushManager.getSubscription()
      if (sub) return { kind: "on" }
    }
  } catch { /* fall through */ }
  return { kind: "off" }
}

async function subscribe(): Promise<State> {
  // Service worker
  const reg = await navigator.serviceWorker.register("/sw.js")
  await navigator.serviceWorker.ready

  // Permission
  const perm = await Notification.requestPermission()
  if (perm === "denied") return { kind: "denied" }
  if (perm !== "granted") return { kind: "off" }

  // Public key from server
  const keyResp = await fetch("/api/push/public-key", { cache: "no-store" })
  if (!keyResp.ok) {
    const t = await keyResp.text()
    throw new Error(`public key fetch failed: ${keyResp.status} ${t}`)
  }
  const { publicKey } = (await keyResp.json()) as { publicKey: string }

  // Subscribe in the browser
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(publicKey).buffer as ArrayBuffer,
  })

  // Tell our server
  const postResp = await fetch("/api/push/subscribe", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(sub.toJSON()),
  })
  if (!postResp.ok) {
    throw new Error(`subscribe POST failed: ${postResp.status}`)
  }
  return { kind: "on" }
}

async function unsubscribe(): Promise<void> {
  const reg = await navigator.serviceWorker.getRegistration()
  if (!reg) return
  const sub = await reg.pushManager.getSubscription()
  if (!sub) return
  await fetch("/api/push/subscribe", {
    method: "DELETE",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ endpoint: sub.endpoint }),
  })
  await sub.unsubscribe()
}

function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4)
  const b64 = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/")
  const bin = atob(b64)
  const out = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i)
  return out
}

function messageOf(e: unknown): string {
  if (e instanceof Error) return e.message
  return String(e)
}
