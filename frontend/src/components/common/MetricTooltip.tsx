interface Props {
  text: string
}

export function MetricTooltip({ text }: Props) {
  return (
    <span className="relative group inline-flex ml-1.5 align-middle">
      <span className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-gray-300 text-xs text-gray-400 cursor-help select-none">
        ?
      </span>
      <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-72 rounded-lg bg-gray-900 px-3 py-2 text-xs text-white leading-relaxed opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-lg">
        {text}
        <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
      </span>
    </span>
  )
}
