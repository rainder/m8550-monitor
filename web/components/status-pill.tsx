type Props = {
  online: boolean
  ageSeconds: number
}

export function StatusPill({ online, ageSeconds }: Props) {
  let label: string
  let cls: string

  if (!online) {
    label = "Router offline"
    cls = "bg-red-900 text-red-200"
  } else if (ageSeconds > 30) {
    label = `Stale (${ageSeconds}s)`
    cls = "bg-amber-900 text-amber-200"
  } else {
    label = "Live"
    cls = "bg-green-900 text-green-200"
  }

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {label}
    </span>
  )
}
