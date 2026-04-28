"use client"

type Props = {
  values: (number | null)[]
  stroke: string
  fill?: string
  width?: number
  height?: number
}

/**
 * Tiny SVG sparkline. Renders a smooth path through `values`, with an optional
 * gradient fill below. Handles nulls by breaking the line. Pure presentation —
 * no axes, no tooltips, no legend.
 */
export function Sparkline({ values, stroke, fill, width = 96, height = 28 }: Props) {
  const real = values.filter((v): v is number => v !== null)
  if (real.length < 2) {
    return <div style={{ width, height }} className="opacity-40" />
  }
  const min = Math.min(...real)
  const max = Math.max(...real)
  const span = Math.max(1, max - min)

  const stepX = width / Math.max(1, values.length - 1)
  const y = (v: number) => height - ((v - min) / span) * (height - 2) - 1

  // Build segments split on nulls.
  const segments: string[] = []
  let current = ""
  values.forEach((v, i) => {
    const x = i * stepX
    if (v === null) {
      if (current) segments.push(current)
      current = ""
      return
    }
    current += current ? ` L${x.toFixed(1)},${y(v).toFixed(1)}` : `M${x.toFixed(1)},${y(v).toFixed(1)}`
  })
  if (current) segments.push(current)

  const lastReal = values
    .map((v, i): [number | null, number] => [v, i])
    .filter(([v]) => v !== null) as [number, number][]
  const lastX = lastReal.length ? lastReal[lastReal.length - 1][1] * stepX : 0
  const lastY = lastReal.length ? y(lastReal[lastReal.length - 1][0]) : height

  const gradId = `spark-${stroke.replace("#", "")}`

  // Build a single area path using the last segment for the fill.
  const lastSegment = segments[segments.length - 1] ?? ""
  const areaPath = lastSegment
    ? `${lastSegment} L${lastX.toFixed(1)},${height} L${lastReal[0][1] * stepX},${height} Z`
    : ""

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="overflow-visible">
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={fill ?? stroke} stopOpacity="0.32" />
          <stop offset="100%" stopColor={fill ?? stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      {areaPath && <path d={areaPath} fill={`url(#${gradId})`} />}
      {segments.map((d, i) => (
        <path key={i} d={d} fill="none" stroke={stroke} strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round" />
      ))}
      {lastReal.length > 0 && (
        <circle cx={lastX} cy={lastY} r="1.75" fill={stroke} />
      )}
    </svg>
  )
}
