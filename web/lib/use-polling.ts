import { useEffect, useRef } from "react"

type Fetcher = (signal: AbortSignal) => Promise<void>

interface Options {
  enabled?: boolean
  /** When this value changes, re-mount the effect: cancel in-flight fetches,
   * fire an immediate poll, and reset the interval. */
  triggerKey?: unknown
}

/**
 * Polls `fetcher` once on mount, then every `intervalMs`. Re-fires immediately
 * when the tab regains visibility or the device comes back online — mobile
 * PWAs pause timers in the background and a backgrounded fetch may hang
 * forever, so without these hooks the UI can stay stuck on stale "offline"
 * state until the user manually reloads.
 */
export function usePolling(
  fetcher: Fetcher,
  intervalMs: number,
  options: Options = {},
): void {
  const { enabled = true, triggerKey } = options
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  useEffect(() => {
    if (!enabled) return
    const controller = new AbortController()
    const run = () => {
      void fetcherRef.current(controller.signal).catch((err) => {
        if (err instanceof Error && err.name === "AbortError") return
        // transient errors are intentionally swallowed: last good state stays
      })
    }
    run()
    const id = setInterval(run, intervalMs)
    const onVisible = () => {
      if (document.visibilityState === "visible") run()
    }
    document.addEventListener("visibilitychange", onVisible)
    window.addEventListener("online", run)
    return () => {
      controller.abort()
      clearInterval(id)
      document.removeEventListener("visibilitychange", onVisible)
      window.removeEventListener("online", run)
    }
  }, [intervalMs, enabled, triggerKey])
}
