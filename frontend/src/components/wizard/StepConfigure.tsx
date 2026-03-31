/**
 * Step 1 — Configure channels, budget, constraints
 * Full implementation in Phase 6.
 */
import type { UploadResponse } from '@/types/upload'

interface Props {
  upload: UploadResponse
  onComplete: () => void
  onRunCreated: (runId: string) => void
}

export function StepConfigure({ upload: _upload, onComplete: _onComplete, onRunCreated: _onRunCreated }: Props) {
  return (
    <div className="flex h-full items-center justify-center p-12">
      <p className="text-gray-400 text-sm">Configure step — Phase 6</p>
    </div>
  )
}
