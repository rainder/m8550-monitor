/**
 * Always render in MB/s for consistency across the dashboard. Two decimals
 * normally; three decimals for sub-1 MB/s values so very low rates don't
 * collapse to "0.00".
 */
export function formatRate(bytesPerSec: number | null): string {
  if (bytesPerSec === null) return "—"
  const mb = bytesPerSec / 1_000_000
  if (mb === 0) return "0.00 MB/s"
  if (mb < 1) return `${mb.toFixed(3)} MB/s`
  return `${mb.toFixed(2)} MB/s`
}

/** Split a rate into [number, unit] so callers can layout them with different styles. */
export function splitRate(bytesPerSec: number | null): [string, string] {
  if (bytesPerSec === null) return ["—", ""]
  const mb = bytesPerSec / 1_000_000
  if (mb === 0) return ["0.00", "MB/s"]
  if (mb < 1) return [mb.toFixed(3), "MB/s"]
  return [mb.toFixed(2), "MB/s"]
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
