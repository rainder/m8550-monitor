import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { act, render } from "@testing-library/react"

import { usePolling } from "../lib/use-polling"

function Probe({ fetcher }: { fetcher: (signal: AbortSignal) => Promise<void> }) {
  usePolling(fetcher, 5000)
  return null
}

describe("usePolling", () => {
  beforeEach(() => {
    vi.useFakeTimers()
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => "visible",
    })
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it("polls on mount, on interval, and re-polls on visibilitychange when becoming visible", async () => {
    const fetcher = vi.fn(async () => {})
    render(<Probe fetcher={fetcher} />)

    // Mount poll
    expect(fetcher).toHaveBeenCalledTimes(1)

    // Interval tick
    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    expect(fetcher).toHaveBeenCalledTimes(2)

    // Hidden → visible should trigger an immediate poll
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => "hidden",
    })
    await act(async () => { document.dispatchEvent(new Event("visibilitychange")) })
    expect(fetcher).toHaveBeenCalledTimes(2) // hidden doesn't trigger

    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => "visible",
    })
    await act(async () => { document.dispatchEvent(new Event("visibilitychange")) })
    expect(fetcher).toHaveBeenCalledTimes(3)
  })

  it("re-polls on window 'online' event", async () => {
    const fetcher = vi.fn(async () => {})
    render(<Probe fetcher={fetcher} />)

    expect(fetcher).toHaveBeenCalledTimes(1)
    await act(async () => { window.dispatchEvent(new Event("online")) })
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it("aborts in-flight fetches on unmount", async () => {
    let captured: AbortSignal | null = null
    const fetcher = vi.fn(async (signal: AbortSignal) => {
      captured = signal
      await new Promise(() => {}) // hang forever
    })
    const { unmount } = render(<Probe fetcher={fetcher} />)
    expect(captured).not.toBeNull()
    expect(captured!.aborted).toBe(false)
    unmount()
    expect(captured!.aborted).toBe(true)
  })
})
