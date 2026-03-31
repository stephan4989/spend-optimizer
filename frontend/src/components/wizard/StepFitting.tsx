import { useEffect } from 'react'
import { useRunsStore } from '@/store/runsStore'
import { useRunPolling } from '@/hooks/useRunPolling'
import { ProgressBar } from '@/components/common/ProgressBar'
import { ErrorBanner } from '@/components/common/ErrorBanner'

interface Props {
  runId: string
  onComplete: () => void
}

const STATUS_MESSAGES: Record<string, string> = {
  queued:     'Waiting to start…',
  fitting:    'Running Bayesian Media Mix Model (this takes a few minutes)…',
  optimizing: 'Optimising budget allocation…',
  completed:  'Done!',
  failed:     'Run failed.',
}

export function StepFitting({ runId, onComplete }: Props) {
  useRunPolling(runId)

  const run = useRunsStore((s) => s.runs.find((r) => r.run_id === runId))

  useEffect(() => {
    if (run?.status === 'completed') onComplete()
  }, [run?.status, onComplete])

  const status = run?.status ?? 'queued'
  const progress = run?.progress_pct ?? 0

  if (status === 'failed') {
    return (
      <div className="mx-auto max-w-lg px-8 py-16">
        <ErrorBanner message={run?.error_message ?? 'The model run failed for an unknown reason.'} />
        <p className="mt-4 text-sm text-gray-500 text-center">
          You can start a new run from the sidebar.
        </p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-lg px-8 py-16">
      <div className="text-center mb-8">
        {/* Spinner */}
        <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-full bg-brand-100">
          <svg className="h-8 w-8 animate-spin text-brand-600" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>
        <h2 className="text-lg font-semibold text-gray-900">Fitting the model</h2>
        <p className="mt-2 text-sm text-gray-500">{STATUS_MESSAGES[status]}</p>
      </div>

      <ProgressBar pct={progress} label="Progress" />

      {/* Phase indicators */}
      <div className="mt-8 space-y-3">
        {[
          { key: 'queued',     label: 'Queued',                  threshold: 0  },
          { key: 'fitting',    label: 'Bayesian MCMC sampling',  threshold: 10 },
          { key: 'optimizing', label: 'Budget optimisation',     threshold: 82 },
          { key: 'completed',  label: 'Results ready',           threshold: 100 },
        ].map(({ key, label, threshold }) => {
          const done = progress > threshold || status === 'completed'
          const active = status === key
          return (
            <div key={key} className={`flex items-center gap-3 text-sm ${done || active ? 'text-gray-800' : 'text-gray-400'}`}>
              <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs
                ${done ? 'bg-brand-600 text-white' : active ? 'border-2 border-brand-500 text-brand-600' : 'border border-gray-300 text-gray-400'}`}>
                {done ? '✓' : ''}
              </span>
              {label}
            </div>
          )
        })}
      </div>

      <p className="mt-8 text-center text-xs text-gray-400">
        You can safely close this page — the model will keep running and results will appear in the sidebar.
      </p>
    </div>
  )
}
