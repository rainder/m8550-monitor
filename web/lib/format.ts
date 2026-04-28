export function formatRate(bytesPerSec: number | null): string {
  if (bytesPerSec === null) return "—"
  if (bytesPerSec < 1000) return `${bytesPerSec} B/s`
  if (bytesPerSec < 1000 * 1000) return `${(bytesPerSec / 1000).toFixed(1)} KB/s`
  if (bytesPerSec < 1000 * 1000 * 1000) return `${(bytesPerSec / (1000 * 1000)).toFixed(2)} MB/s`
  return `${(bytesPerSec / (1000 * 1000 * 1000)).toFixed(2)} GB/s`
}
