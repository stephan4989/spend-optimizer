import type { RunStatus } from '@/types/run'

interface Props {
  status: RunStatus
}

const CONFIG: Record<RunStatus, { label: string; classes: string; dot: string }> = {
  queued:     { label: 'Queued',     classes: 'bg-gray-100 text-gray-600',    dot: 'bg-gray-400' },
  fitting:    { label: 'Fitting',    classes: 'bg-blue-100 text-blue-700',    dot: 'bg-blue-500 animate-pulse' },
  optimizing: { label: 'Optimizing',classes: 'bg-purple-100 text-purple-700',dot: 'bg-purple-500 animate-pulse' },
  completed:  { label: 'Completed', classes: 'bg-green-100 text-green-700',  dot: 'bg-green-500' },
  failed:     { label: 'Failed',    classes: 'bg-red-100 text-red-700',      dot: 'bg-red-500' },
}

export function RunStatusBadge({ status }: Props) {
  const { label, classes, dot } = CONFIG[status] ?? CONFIG.queued
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${classes}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {label}
    </span>
  )
}
