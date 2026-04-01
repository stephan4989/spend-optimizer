import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createRun } from '@/api/runs'
import { useSessionStore } from '@/store/sessionStore'
import { useRunsStore } from '@/store/runsStore'
import type { UploadResponse } from '@/types/upload'
import type { ChannelConstraint, MeridianConfig } from '@/types/run'
import { DEFAULT_MERIDIAN_CONFIG } from '@/types/run'
import { ErrorBanner } from '@/components/common/ErrorBanner'

interface Props {
  upload: UploadResponse
  onComplete: () => void
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value)
}

export function StepConfigure({ upload, onComplete }: Props) {
  const sessionId = useSessionStore((s) => s.sessionId)!
  const { upsertRun } = useRunsStore()
  const navigate = useNavigate()

  const [runLabel, setRunLabel] = useState('')
  const [totalBudget, setTotalBudget] = useState<string>(() => {
    // Default: sum of historical spend per channel
    const total = Object.values(upload.total_spend_per_channel).reduce((a, b) => a + b, 0)
    return Math.round(total).toString()
  })
  const [selectedChannels, setSelectedChannels] = useState<string[]>(upload.channels)
  const [constraints, setConstraints] = useState<Record<string, ChannelConstraint>>(() =>
    Object.fromEntries(upload.channels.map((ch) => [ch, { min_fraction: 0, max_fraction: 1 }]))
  )
  const [showConstraints, setShowConstraints] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [meridianConfig, setMeridianConfig] = useState<MeridianConfig>(DEFAULT_MERIDIAN_CONFIG)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function toggleChannel(ch: string) {
    setSelectedChannels((prev) =>
      prev.includes(ch) ? prev.filter((c) => c !== ch) : [...prev, ch]
    )
  }

  function updateConstraint(ch: string, field: keyof ChannelConstraint, raw: string) {
    const val = Math.max(0, Math.min(1, parseFloat(raw) / 100 || 0))
    setConstraints((prev) => ({ ...prev, [ch]: { ...prev[ch], [field]: val } }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!runLabel.trim()) { setError('Please enter a name for this run.'); return }
    const budget = parseFloat(totalBudget)
    if (!budget || budget <= 0) { setError('Please enter a valid total budget.'); return }
    if (selectedChannels.length === 0) { setError('Select at least one channel.'); return }

    setSubmitting(true)
    setError(null)
    try {
      const run = await createRun(sessionId, {
        upload_id: upload.upload_id,
        run_label: runLabel.trim(),
        total_budget: budget,
        channel_names: selectedChannels,
        channel_constraints: Object.fromEntries(
          selectedChannels.map((ch) => [ch, constraints[ch] ?? { min_fraction: 0, max_fraction: 1 }])
        ),
        meridian_config: meridianConfig,
      })
      upsertRun({
        run_id: run.run_id,
        run_label: run.run_label,
        status: run.status,
        created_at: run.created_at,
        completed_at: null,
        progress_pct: 0,
        error_message: null,
      })
      onComplete()
      navigate(`/runs/${run.run_id}`, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start run. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-8 py-10">
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-gray-900">Configure model run</h2>
        <p className="mt-1 text-sm text-gray-500">
          Set your budget and channel options, then start the model.
        </p>
      </div>

      {Object.keys(upload.column_renames ?? {}).length > 0 && (
        <div className="mb-5 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
          <span className="font-medium">Columns were automatically renamed</span> to match the required format:{' '}
          {Object.entries(upload.column_renames).map(([from, to], i) => (
            <span key={from}>
              {i > 0 && ', '}
              <span className="font-mono">{from}</span> → <span className="font-mono">{to}</span>
            </span>
          ))}
        </div>
      )}

      {error && (
        <div className="mb-5">
          <ErrorBanner message={error} onDismiss={() => setError(null)} />
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Run label */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            Run name <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={runLabel}
            onChange={(e) => setRunLabel(e.target.value)}
            placeholder="e.g. Germany Q1 2024"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>

        {/* Upload summary */}
        <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-xs text-gray-500">
          <span className="font-medium text-gray-700">{upload.filename}</span>
          {' · '}{upload.rows} rows · {upload.granularity} · {upload.date_range.start} → {upload.date_range.end}
        </div>

        {/* Total budget */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            Optimisation budget <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <span className="absolute inset-y-0 left-3 flex items-center text-gray-400 text-sm">$</span>
            <input
              type="number"
              min="1"
              value={totalBudget}
              onChange={(e) => setTotalBudget(e.target.value)}
              className="w-full rounded-lg border border-gray-300 pl-7 pr-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </div>
          <p className="mt-1 text-xs text-gray-400">
            Historical total: {formatCurrency(Object.values(upload.total_spend_per_channel).reduce((a, b) => a + b, 0))}
          </p>
        </div>

        {/* Channel selection */}
        <div>
          <p className="mb-2 text-sm font-medium text-gray-700">Channels to include</p>
          <div className="flex flex-wrap gap-2">
            {upload.channels.map((ch) => (
              <button
                key={ch}
                type="button"
                onClick={() => toggleChannel(ch)}
                className={`rounded-full px-3 py-1 text-xs font-medium border transition-colors ${
                  selectedChannels.includes(ch)
                    ? 'bg-brand-600 border-brand-600 text-white'
                    : 'bg-white border-gray-300 text-gray-600 hover:border-brand-400'
                }`}
              >
                {ch}
              </button>
            ))}
          </div>
        </div>

        {/* Per-channel constraints (collapsible) */}
        <div className="rounded-lg border border-gray-200">
          <button
            type="button"
            onClick={() => setShowConstraints((v) => !v)}
            className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium text-gray-700"
          >
            <span>Per-channel budget constraints <span className="ml-1 text-xs font-normal text-gray-400">(optional)</span></span>
            <svg className={`h-4 w-4 transition-transform ${showConstraints ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
            </svg>
          </button>
          {showConstraints && (
            <div className="border-t border-gray-200 divide-y divide-gray-100">
              {selectedChannels.map((ch) => (
                <div key={ch} className="px-4 py-3">
                  <p className="mb-2 text-xs font-medium text-gray-700">{ch}</p>
                  <div className="grid grid-cols-2 gap-4">
                    {(['min_fraction', 'max_fraction'] as const).map((field) => (
                      <div key={field}>
                        <label className="text-xs text-gray-500">{field === 'min_fraction' ? 'Min %' : 'Max %'}</label>
                        <input
                          type="number"
                          min="0"
                          max="100"
                          step="1"
                          value={Math.round((constraints[ch]?.[field] ?? (field === 'min_fraction' ? 0 : 1)) * 100)}
                          onChange={(e) => updateConstraint(ch, field, e.target.value)}
                          className="mt-0.5 w-full rounded border border-gray-300 px-2 py-1 text-xs focus:border-brand-500 focus:outline-none"
                        />
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Advanced Meridian settings (collapsible) */}
        <div className="rounded-lg border border-gray-200">
          <button
            type="button"
            onClick={() => setShowAdvanced((v) => !v)}
            className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium text-gray-700"
          >
            <span>Advanced model settings <span className="ml-1 text-xs font-normal text-gray-400">(optional)</span></span>
            <svg className={`h-4 w-4 transition-transform ${showAdvanced ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
            </svg>
          </button>
          {showAdvanced && (
            <div className="border-t border-gray-200 px-4 py-4 grid grid-cols-3 gap-4">
              {([
                { key: 'n_chains', label: 'Chains', min: 1, max: 8 },
                { key: 'n_warmup', label: 'Warmup steps', min: 100, max: 2000 },
                { key: 'n_samples', label: 'Samples', min: 100, max: 4000 },
              ] as const).map(({ key, label, min, max }) => (
                <div key={key}>
                  <label className="text-xs text-gray-500">{label}</label>
                  <input
                    type="number"
                    min={min}
                    max={max}
                    value={meridianConfig[key]}
                    onChange={(e) => setMeridianConfig((c) => ({ ...c, [key]: parseInt(e.target.value) || c[key] }))}
                    className="mt-0.5 w-full rounded border border-gray-300 px-2 py-1 text-xs focus:border-brand-500 focus:outline-none"
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Submit */}
        <div className="flex justify-end gap-3 pt-2">
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60 transition-colors"
          >
            {submitting ? (
              <>
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Starting…
              </>
            ) : (
              <>
                Run Model
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.972l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
                </svg>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  )
}
