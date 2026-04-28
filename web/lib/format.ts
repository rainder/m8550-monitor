export function formatRate(bytesPerSec: number | null): string {
  if (bytesPerSec === null) return "—"
  if (bytesPerSec < 1000) return `${bytesPerSec} B/s`
  if (bytesPerSec < 1000 * 1000) return `${(bytesPerSec / 1000).toFixed(1)} KB/s`
  if (bytesPerSec < 1000 * 1000 * 1000) return `${(bytesPerSec / (1000 * 1000)).toFixed(2)} MB/s`
  return `${(bytesPerSec / (1000 * 1000 * 1000)).toFixed(2)} GB/s`
}

/** Split a rate into [number, unit] so callers can layout them with different styles. */
export function splitRate(bytesPerSec: number | null): [string, string] {
  if (bytesPerSec === null) return ["—", ""]
  if (bytesPerSec < 1000) return [String(bytesPerSec), "B/s"]
  if (bytesPerSec < 1000 * 1000) return [(bytesPerSec / 1000).toFixed(1), "KB/s"]
  if (bytesPerSec < 1000 * 1000 * 1000) return [(bytesPerSec / (1000 * 1000)).toFixed(2), "MB/s"]
  return [(bytesPerSec / (1000 * 1000 * 1000)).toFixed(2), "GB/s"]
}

/** Cumulative bytes — base-1000, one decimal, never below 1 KB. */
export function formatBytes(bytes: number | null): string {
  if (bytes === null) return "—"
  if (bytes < 1000) return `${bytes} B`
  if (bytes < 1000 * 1000) return `${(bytes / 1000).toFixed(1)} KB`
  if (bytes < 1000 * 1000 * 1000) return `${(bytes / (1000 * 1000)).toFixed(1)} MB`
  if (bytes < 1000 * 1000 * 1000 * 1000) return `${(bytes / 1e9).toFixed(2)} GB`
  return `${(bytes / 1e12).toFixed(2)} TB`
}

/** "5s ago", "2m ago" — terse, for last-updated indicators. */
export function formatRelative(seconds: number): string {
  if (seconds < 1) return "now"
  if (seconds < 60) return `${seconds}s ago`
  const m = Math.floor(seconds / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  return `${h}h ago`
}
