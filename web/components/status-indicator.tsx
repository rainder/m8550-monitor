type Props = {
  online: boolean
  ageSeconds: number
}

/**
 * Vercel-style status row: small pulsing dot + label. No box, no padding —
 * sits inline with surrounding type.
 */
export function StatusIndicator({ online, ageSeconds }: Props) {
  let label: string
  let colour: string
  let pulsing = false

  if (!online) {
    label = "Router offline"
    colour = "bg-red-500"
  } else if (ageSeconds > 30) {
    label = `Stale · ${ageSeconds}s`
    colour = "bg-amber-500"
  } else {
    label = "Live"
    colour = "bg-green-500"
    pulsing = true
  }

  return (
    <div className="flex items-center gap-2 text-xs text-zinc-400">
      <span className="relative flex h-1.5 w-1.5">
        {pulsing && <span className="absolute inline-flex h-full w-full rounded-full bg-green-500 opacity-75 dot-pulse" />}
        <span className={`relative inline-flex h-1.5 w-1.5 rounded-full ${colour}`} />
      </span>
      <span className="font-mono uppercase tracking-wider">{label}</span>
    </div>
  )
}
