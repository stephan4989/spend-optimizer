import { useState } from 'react'
import { useSessionStore } from '@/store/sessionStore'
import { optimiseScenario } from '@/api/results'
import type { RunResults, ScenarioResult } from '@/types/results'

interface Props {
  run_id: string
  results: RunResults
}

function fmtCurrency(n: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n)
}

function fmtPct(n: number) {
  return `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`
}

function fmt(n: number) {
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(n)
}

export function ScenarioPanel({ run_id, results }: Props) {
  const sessionId = useSessionStore((s) => s.sessionId)!

  // Default to the original optimised budget
  const originalBudget = Object.values(results.optimized_allocation).reduce((a, b) => a + b, 0)
  const [budget, setBudget] = useState(Math.round(originalBudget))
  const [inputValue, setInputValue] = useState(String(Math.round(originalBudget)))
  const [scenario, setScenario] = useState<ScenarioResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Slider range: 25% → 200% of original budget
  const sliderMin = Math.round(originalBudget * 0.25)
  const sliderMax = Math.round(originalBudget * 2.0)

  async function handleRun() {
    const b = parseFloat(inputValue)
    if (!b || b <= 0) { setError('Enter a valid budget greater than 0.'); return }
    setLoading(true)
    setError(null)
    try {
      const result = await optimiseScenario(sessionId, run_id, b)
      setScenario(result)
      setBudget(b)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Optimisation failed.')
    } finally {
      setLoading(false)
    }
  }

  const pctOfOriginal = ((parseFloat(inputValue) || originalBudget) / originalBudget - 1) * 100

  return (
    <div className="rounded-xl border border-brand-200 bg-brand-50 p-6 space-y-5">
      <div>
        <h3 className="text-sm font-semibold text-gray-800">Budget scenario</h3>
        <p className="mt-0.5 text-xs text-gray-500">
          Adjust the total budget to see how the optimal allocation and estimated acquisitions change — no refitting needed.
        </p>
      </div>

      {/* Slider + input */}
      <div className="space-y-3">
        <div className="flex items-center gap-4">
          <input
            type="range"
            min={sliderMin}
            max={sliderMax}
            step={1000}
            value={parseFloat(inputValue) || originalBudget}
            onChange={(e) => {
              const v = e.target.value
              setInputValue(v)
            }}
            className="flex-1 accent-brand-600"
          />
          <div className="relative w-40">
            <span className="absolute inset-y-0 left-3 flex items-center text-gray-400 text-sm">$</span>
            <input
              type="number"
              min="1"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              className="w-full rounded-lg border border-gray-300 pl-7 pr-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </div>
        </div>

        {/* Change vs original label */}
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>{fmtCurrency(sliderMin)}</span>
          <span className={`font-medium ${pctOfOriginal > 0 ? 'text-green-600' : pctOfOriginal < 0 ? 'text-red-600' : 'text-gray-500'}`}>
            {pctOfOriginal === 0
              ? 'Same as original'
              : `${pctOfOriginal > 0 ? '+' : ''}${pctOfOriginal.toFixed(0)}% vs original budget`}
          </span>
          <span>{fmtCurrency(sliderMax)}</span>
        </div>
      </div>

      {error && <p className="text-xs text-red-600">{error}</p>}

      <button
        onClick={handleRun}
        disabled={loading}
        className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-5 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60 transition-colors"
      >
        {loading ? (
          <><span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" /> Optimising…</>
        ) : 'Run scenario'}
      </button>

      {/* Results */}
      {scenario && (
        <div className="border-t border-brand-200 pt-5 space-y-4">
          {/* Summary cards */}
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-lg border border-gray-200 bg-white p-4">
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Budget</p>
              <p className="mt-1.5 text-xl font-bold text-gray-900">{fmtCurrency(scenario.total_budget)}</p>
            </div>
            <div className="rounded-lg border border-gray-200 bg-white p-4">
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Est. acquisitions</p>
              <p className="mt-1.5 text-xl font-bold text-gray-900">{fmt(scenario.optimized_total_acquisitions)}</p>
              <p className="text-xs text-gray-400">vs {fmt(scenario.prior_total_acquisitions)} at prior mix</p>
            </div>
            <div className={`rounded-lg border p-4 ${scenario.lift_pct >= 0 ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}`}>
              <p className={`text-xs font-medium uppercase tracking-wide ${scenario.lift_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>Lift vs prior mix</p>
              <p className={`mt-1.5 text-xl font-bold ${scenario.lift_pct >= 0 ? 'text-green-700' : 'text-red-700'}`}>{fmtPct(scenario.lift_pct)}</p>
            </div>
          </div>

          {/* Allocation table */}
          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
            <table className="min-w-full divide-y divide-gray-100 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Channel</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">Optimised spend</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">Share</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">vs original run</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {results.channels.map((ch) => {
                  const newSpend = scenario.optimized_allocation[ch] ?? 0
                  const origSpend = results.optimized_allocation[ch] ?? 0
                  const delta = newSpend - origSpend
                  const share = scenario.total_budget > 0 ? (newSpend / scenario.total_budget) * 100 : 0
                  return (
                    <tr key={ch} className="hover:bg-gray-50">
                      <td className="px-4 py-2 font-medium text-gray-900">{ch}</td>
                      <td className="px-4 py-2 text-right text-gray-700">{fmtCurrency(newSpend)}</td>
                      <td className="px-4 py-2 text-right text-gray-500">{share.toFixed(1)}%</td>
                      <td className={`px-4 py-2 text-right font-medium ${delta >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {delta >= 0 ? '+' : ''}{fmtCurrency(delta)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
              <tfoot className="bg-gray-50 border-t border-gray-200">
                <tr>
                  <td className="px-4 py-2 text-xs font-semibold text-gray-600">Total</td>
                  <td className="px-4 py-2 text-right text-xs font-semibold text-gray-600">{fmtCurrency(scenario.total_budget)}</td>
                  <td className="px-4 py-2 text-right text-xs text-gray-400">100%</td>
                  <td className="px-4 py-2 text-right text-xs font-semibold text-gray-600">
                    {(() => { const d = scenario.total_budget - originalBudget; return `${d >= 0 ? '+' : ''}${fmtCurrency(d)}` })()}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
