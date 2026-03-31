interface Props {
  pct: number          // 0–100
  label?: string
  animated?: boolean
}

export function ProgressBar({ pct, label, animated = true }: Props) {
  const clamped = Math.max(0, Math.min(100, pct))
  return (
    <div className="w-full">
      {label && (
        <div className="mb-1.5 flex justify-between text-xs text-gray-500">
          <span>{label}</span>
          <span>{clamped}%</span>
        </div>
      )}
      <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100">
        <div
          className={`h-full rounded-full bg-brand-500 transition-all duration-500 ${animated && clamped < 100 ? 'animate-pulse' : ''}`}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  )
}
