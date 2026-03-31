/**
 * Step 0 — Upload CSV
 * Full implementation in Phase 6.
 */
import type { UploadResponse } from '@/types/upload'

interface Props {
  onComplete: (upload: UploadResponse) => void
}

export function StepUpload({ onComplete: _onComplete }: Props) {
  return (
    <div className="flex h-full items-center justify-center p-12">
      <p className="text-gray-400 text-sm">Upload step — Phase 6</p>
    </div>
  )
}
