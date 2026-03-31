/**
 * Step 3 — Results: charts + allocation table
 * Full implementation in Phase 7.
 */
import type { RunResults } from '@/types/results'
import type { RunSummary } from '@/types/run'

interface Props {
  run: RunSummary
  results: RunResults | null
}

export function StepResults({ run: _run, results: _results }: Props) {
  return (
    <div className="flex h-full items-center justify-center p-12">
      <p className="text-gray-400 text-sm">Results step — Phase 7</p>
    </div>
  )
}
