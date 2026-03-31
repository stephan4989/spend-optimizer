/**
 * WizardShell — Phase 6
 *
 * Hosts the 4-step new-run wizard:
 *   Step 0: Upload CSV
 *   Step 1: Configure (channels, budget, constraints)
 *   Step 2: Fitting (progress bar while Celery runs)
 *   Step 3: Results (charts + allocation table)
 *
 * Currently a placeholder; full implementation in Phase 6.
 */
import { StepUpload } from './StepUpload'
import { StepConfigure } from './StepConfigure'
import { StepFitting } from './StepFitting'
import { StepResults } from './StepResults'
import { useRunsStore } from '@/store/runsStore'
import { useState } from 'react'
import type { UploadResponse } from '@/types/upload'

interface Props {
  runId: string
}

const STEP_LABELS = ['Upload', 'Configure', 'Fitting', 'Results']

export function WizardShell({ runId }: Props) {
  const run = useRunsStore((s) => s.runs.find((r) => r.run_id === runId))
  const results = useRunsStore((s) => s.results[runId])

  // Local wizard state — persists for this session page visit only
  const [step, setStep] = useState<number>(() => {
    if (!run) return 0
    if (run.status === 'completed' || run.status === 'failed') return 3
    if (run.status === 'fitting' || run.status === 'optimizing' || run.status === 'queued') return 2
    return 1
  })
  const [upload, setUpload] = useState<UploadResponse | null>(null)

  function handleUploadComplete(u: UploadResponse) {
    setUpload(u)
    setStep(1)
  }

  function handleConfigureComplete() {
    setStep(2)
  }

  function handleFittingComplete() {
    setStep(3)
  }

  return (
    <div className="flex h-full flex-col">
      {/* Step progress bar */}
      <div className="border-b border-gray-200 bg-white px-8 py-4">
        <nav className="flex items-center gap-0">
          {STEP_LABELS.map((label, i) => (
            <div key={label} className="flex items-center">
              <div className={`flex items-center gap-2 ${i < step ? 'text-brand-600' : i === step ? 'text-gray-900' : 'text-gray-400'}`}>
                <span className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold
                  ${i < step ? 'bg-brand-600 text-white' : i === step ? 'bg-gray-900 text-white' : 'bg-gray-200 text-gray-500'}`}>
                  {i < step ? '✓' : i + 1}
                </span>
                <span className="text-sm font-medium">{label}</span>
              </div>
              {i < STEP_LABELS.length - 1 && (
                <div className={`mx-3 h-px w-8 ${i < step ? 'bg-brand-600' : 'bg-gray-200'}`} />
              )}
            </div>
          ))}
        </nav>
      </div>

      {/* Step content */}
      <div className="flex-1 overflow-y-auto">
        {step === 0 && <StepUpload onComplete={handleUploadComplete} />}
        {step === 1 && upload && (
          <StepConfigure
            upload={upload}
            onComplete={handleConfigureComplete}
            onRunCreated={(id) => {
              // Navigate happens inside StepConfigure after creating the run
              void id
            }}
          />
        )}
        {step === 2 && <StepFitting runId={runId} onComplete={handleFittingComplete} />}
        {step === 3 && run && (
          <StepResults run={run} results={results ?? null} />
        )}
      </div>
    </div>
  )
}
