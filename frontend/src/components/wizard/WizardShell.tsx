/**
 * WizardShell — orchestrates the 4-step run wizard.
 *
 * Two modes:
 *  - newRun=true  (at /new): shows steps 0 (Upload) + 1 (Configure).
 *    After Configure creates the run it navigates to /runs/:runId.
 *  - newRun=false (at /runs/:runId): shows step 2 (Fitting) or 3 (Results)
 *    depending on the run status from the store.
 */
import { useState } from 'react'
import type { UploadResponse } from '@/types/upload'
import { useRunsStore } from '@/store/runsStore'
import { StepUpload } from './StepUpload'
import { StepConfigure } from './StepConfigure'
import { StepFitting } from './StepFitting'
import { StepResults } from './StepResults'

interface NewRunProps {
  newRun: true
}

interface ExistingRunProps {
  newRun?: false
  runId: string
}

type Props = NewRunProps | ExistingRunProps

const STEP_LABELS = ['Upload', 'Configure', 'Fitting', 'Results']

function StepIndicator({ current }: { current: number }) {
  return (
    <div className="border-b border-gray-200 bg-white px-8 py-4">
      <nav className="flex items-center gap-0">
        {STEP_LABELS.map((label, i) => (
          <div key={label} className="flex items-center">
            <div className={`flex items-center gap-2 ${i < current ? 'text-brand-600' : i === current ? 'text-gray-900' : 'text-gray-400'}`}>
              <span className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold
                ${i < current ? 'bg-brand-600 text-white' : i === current ? 'bg-gray-900 text-white' : 'bg-gray-200 text-gray-500'}`}>
                {i < current ? '✓' : i + 1}
              </span>
              <span className="text-sm font-medium">{label}</span>
            </div>
            {i < STEP_LABELS.length - 1 && (
              <div className={`mx-3 h-px w-8 ${i < current ? 'bg-brand-600' : 'bg-gray-200'}`} />
            )}
          </div>
        ))}
      </nav>
    </div>
  )
}

/** New run: steps 0 → 1, then navigate to /runs/:runId */
function NewRunWizard() {
  const [step, setStep] = useState(0)
  const [upload, setUpload] = useState<UploadResponse | null>(null)

  return (
    <div className="flex h-full flex-col">
      <StepIndicator current={step} />
      <div className="flex-1 overflow-y-auto">
        {step === 0 && (
          <StepUpload onComplete={(u) => { setUpload(u); setStep(1) }} />
        )}
        {step === 1 && upload && (
          <StepConfigure
            upload={upload}
            onComplete={() => {/* navigation handled inside StepConfigure */}}
          />
        )}
      </div>
    </div>
  )
}

/** Existing run: steps 2 → 3 */
function ExistingRunWizard({ runId }: { runId: string }) {
  const run = useRunsStore((s) => s.runs.find((r) => r.run_id === runId))
  const results = useRunsStore((s) => s.results[runId])

  // Determine starting step from run status
  const isTerminal = run?.status === 'completed' || run?.status === 'failed'
  const [step, setStep] = useState(isTerminal ? 3 : 2)

  return (
    <div className="flex h-full flex-col">
      <StepIndicator current={step} />
      <div className="flex-1 overflow-y-auto">
        {step === 2 && (
          <StepFitting runId={runId} onComplete={() => setStep(3)} />
        )}
        {step === 3 && run && (
          <StepResults run={run} results={results ?? null} />
        )}
        {step === 3 && !run && (
          <div className="flex h-full items-center justify-center">
            <div className="h-6 w-6 animate-spin rounded-full border-4 border-brand-500 border-t-transparent" />
          </div>
        )}
      </div>
    </div>
  )
}

export function WizardShell(props: Props) {
  if (props.newRun) return <NewRunWizard />
  return <ExistingRunWizard runId={props.runId} />
}
