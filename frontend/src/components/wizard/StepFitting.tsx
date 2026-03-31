/**
 * Step 2 — Fitting progress
 * Full implementation in Phase 6.
 */
interface Props {
  runId: string
  onComplete: () => void
}

export function StepFitting({ runId: _runId, onComplete: _onComplete }: Props) {
  return (
    <div className="flex h-full items-center justify-center p-12">
      <p className="text-gray-400 text-sm">Fitting step — Phase 6</p>
    </div>
  )
}
