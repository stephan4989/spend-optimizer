import type { RunResults } from '@/types/results'
import type { RunSummary } from '@/types/run'
import { RunStatusBadge } from '@/components/runs/RunStatusBadge'
import { ResponseCurveChart } from '@/components/charts/ResponseCurveChart'
import { BudgetAllocationChart } from '@/components/charts/BudgetAllocationChart'
import { ModelFitChart } from '@/components/charts/ModelFitChart'
import { ContributionChart } from '@/components/charts/ContributionChart'
import { MarginalCPAChart } from '@/components/charts/MarginalCPAChart'
import { MetricTooltip } from '@/components/common/MetricTooltip'
import { ScenarioPanel } from '@/components/wizard/ScenarioPanel'

interface Props {
  run: RunSummary
  results: RunResults | null
}

function fmt(n: number) {
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(n)
}

function fmtCurrency(n: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n)
}

function fmtPct(n: number) {
  return `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`
}

export function StepResults({ run, results }: Props) {
  if (run.status === 'failed') {
    return (
      <div className="mx-auto max-w-lg px-8 py-16 text-center">
        <RunStatusBadge status="failed" />
        <p className="mt-4 text-sm text-gray-500">{run.error_message ?? 'The model run failed.'}</p>
      </div>
    )
  }

  if (!results) {
    return (
      <div className="mx-auto max-w-lg px-8 py-16 text-center">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-brand-500 border-t-transparent" />
        <p className="mt-3 text-sm text-gray-500">Loading results…</p>
      </div>
    )
  }

  const liftPositive = results.lift_pct >= 0
  const totalPrior = Object.values(results.prior_allocation).reduce((a, b) => a + b, 0)
  const totalOptimized = Object.values(results.optimized_allocation).reduce((a, b) => a + b, 0)
  const n = results.n_periods

  return (
    <div className="mx-auto max-w-3xl px-8 py-10 space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">{results.run_label}</h2>
          <p className="mt-1 text-sm text-gray-500">
            {results.channels.length} channels · {results.planning_period_label} plan ({results.n_periods} periods) · Optimisation complete
          </p>
        </div>
        <RunStatusBadge status="completed" />
      </div>

      {/* Planning period budget summary */}
      <div className="rounded-xl border border-brand-200 bg-brand-50 px-5 py-4 flex items-center justify-between">
        <div>
          <p className="text-xs font-medium text-brand-700 uppercase tracking-wide">{results.planning_period_label} budget</p>
          <p className="mt-1 text-2xl font-bold text-brand-900">{fmtCurrency(totalOptimized * n)}</p>
          <p className="mt-0.5 text-xs text-brand-600">{fmtCurrency(totalOptimized)} per period × {n} periods</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-brand-600">Prior mix total</p>
          <p className="text-lg font-semibold text-brand-800">{fmtCurrency(totalPrior * n)}</p>
        </div>
      </div>

      {/* Lift summary cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Prior acquisitions</p>
          <p className="mt-2 text-2xl font-bold text-gray-900">{fmt(results.prior_total_acquisitions)}</p>
          <p className="mt-0.5 text-xs text-gray-400">per period at prior mix</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Optimised acquisitions</p>
          <p className="mt-2 text-2xl font-bold text-gray-900">{fmt(results.optimized_total_acquisitions)}</p>
          <p className="mt-0.5 text-xs text-gray-400">per period at optimised mix</p>
        </div>
        <div className={`rounded-xl border p-5 ${liftPositive ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}`}>
          <p className={`text-xs font-medium uppercase tracking-wide ${liftPositive ? 'text-green-600' : 'text-red-600'}`}>Estimated lift</p>
          <p className={`mt-2 text-2xl font-bold ${liftPositive ? 'text-green-700' : 'text-red-700'}`}>
            {fmtPct(results.lift_pct)}
          </p>
          <p className={`mt-0.5 text-xs ${liftPositive ? 'text-green-500' : 'text-red-500'}`}>vs. prior allocation</p>
        </div>
      </div>

      {/* Budget allocation table */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-800">Budget allocation</h3>
          <ExportButton results={results} />
        </div>
        <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Channel</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">Prior / period</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">Prior share</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">Optimised / period</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">Optimised total</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">Share</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">Change</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {results.channels.map((ch) => {
                const prior = results.prior_allocation[ch] ?? 0
                const optimized = results.optimized_allocation[ch] ?? 0
                const delta = optimized - prior
                const priorShare = totalPrior > 0 ? (prior / totalPrior) * 100 : 0
                const optimizedShare = totalOptimized > 0 ? (optimized / totalOptimized) * 100 : 0
                return (
                  <tr key={ch} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900">{ch}</td>
                    <td className="px-4 py-3 text-right text-gray-600">{fmtCurrency(prior)}</td>
                    <td className="px-4 py-3 text-right text-gray-500">{priorShare.toFixed(1)}%</td>
                    <td className="px-4 py-3 text-right font-medium text-gray-900">{fmtCurrency(optimized)}</td>
                    <td className="px-4 py-3 text-right text-gray-700">{fmtCurrency(optimized * n)}</td>
                    <td className="px-4 py-3 text-right text-gray-500">{optimizedShare.toFixed(1)}%</td>
                    <td className={`px-4 py-3 text-right font-medium ${delta >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {delta >= 0 ? '+' : ''}{fmtCurrency(delta)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
            <tfoot className="bg-gray-50 border-t border-gray-200">
              <tr>
                <td className="px-4 py-2 text-xs font-semibold text-gray-600">Total</td>
                <td className="px-4 py-2 text-right text-xs font-semibold text-gray-600">{fmtCurrency(totalPrior)}</td>
                <td className="px-4 py-2 text-right text-xs text-gray-400">100%</td>
                <td className="px-4 py-2 text-right text-xs font-semibold text-gray-600">{fmtCurrency(totalOptimized)}</td>
                <td className="px-4 py-2 text-right text-xs font-semibold text-gray-600">{fmtCurrency(totalOptimized * n)}</td>
                <td className="px-4 py-2 text-right text-xs text-gray-400">100%</td>
                <td className="px-4 py-2" />
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      {/* ── 1. Model Fit ──────────────────────────────────────────────── */}
      <div>
        <h3 className="mb-1 flex items-center text-sm font-semibold text-gray-800">
          Model fit — actual vs predicted
          <MetricTooltip text="'Predicted' is the posterior mean of total media-attributed acquisitions (Hill-Adstock contributions across all channels). The gap between predicted and actual is the baseline — acquisitions driven by organic traffic, trend, and seasonality. The shaded band is the 80% credible interval across posterior samples." />
        </h3>
        <p className="mb-3 text-xs text-gray-400">Media-attributed acquisitions vs actual — gap between lines is baseline (organic, trend, seasonality)</p>
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          {results.model_fit
            ? <ModelFitChart data={results.model_fit} />
            : <p className="py-8 text-center text-xs text-gray-400">Model fit data not available for this run.</p>
          }
        </div>
      </div>

      {/* ── 2. Channel Contributions ───────────────────────────────── */}
      <div>
        <h3 className="mb-1 flex items-center text-sm font-semibold text-gray-800">
          Channel contribution breakdown
          <MetricTooltip text="Media-attributed acquisitions per channel per period, computed using time-series geometric adstock. Each channel's contribution is the Hill-saturation output scaled by its posterior beta coefficient. The baseline (organic traffic, seasonality, trend) is excluded — contributions shown here are the marginal effect of paid media spend." />
        </h3>
        <p className="mb-3 text-xs text-gray-400">Acquisitions attributed to each channel over time</p>
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          {results.contributions
            ? <ContributionChart data={results.contributions} channels={results.channels} />
            : <p className="py-8 text-center text-xs text-gray-400">Contribution data not available for this run.</p>
          }
        </div>
      </div>

      {/* ── 3. Response Curves ─────────────────────────────────────── */}
      <div>
        <h3 className="mb-1 flex items-center text-sm font-semibold text-gray-800">
          Response curves
          <MetricTooltip text="Spend vs expected acquisitions for each channel, evaluated at steady-state using the Hill-Adstock model. The x-axis is weekly spend; the y-axis is incremental acquisitions expected at that spend level. Shaded bands show the 80% credible interval across posterior samples. Dots mark the current (prior) spend level for each channel." />
        </h3>
        <p className="mb-3 text-xs text-gray-400">Diminishing returns — how each channel converts spend to acquisitions</p>
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <ResponseCurveChart results={results} />
        </div>
      </div>

      {/* ── 4. Marginal CPA ───────────────────────────────────────────── */}
      <div>
        <h3 className="mb-1 flex items-center text-sm font-semibold text-gray-800">
          Marginal CPA by channel
          <MetricTooltip text="Marginal CPA = ΔSpend / ΔAcquisitions between consecutive points on the response curve. It shows the cost of acquiring the next customer as you increase spend. A rising curve means diminishing returns — each additional dollar buys fewer acquisitions. The optimal budget splits spend across channels until their marginal CPAs are equal (the Lagrangian condition the optimizer solves)." />
        </h3>
        <p className="mb-3 text-xs text-gray-400">Cost of the next acquisition as spend increases — where efficiency breaks down</p>
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <MarginalCPAChart results={results} />
        </div>
      </div>

      {/* Budget allocation chart */}
      <div>
        <h3 className="mb-3 text-sm font-semibold text-gray-800">Budget allocation comparison</h3>
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <BudgetAllocationChart results={results} />
        </div>
      </div>

      {/* Budget scenario */}
      <ScenarioPanel run_id={results.run_id} results={results} />

      {/* ── Model diagnostics ─────────────────────────────────────── */}
      <div>
        <h3 className="mb-3 flex items-center text-sm font-semibold text-gray-800">
          Model diagnostics
          <MetricTooltip text="MCMC convergence and sample quality metrics. R-hat measures chain mixing — values < 1.1 indicate the chains have converged. ESS (effective sample size) measures how many independent samples the chains are equivalent to — higher is better. WAIC (Widely Applicable Information Criterion) measures out-of-sample predictive accuracy relative to other runs of the same model — lower is better." />
        </h3>
        <div className="grid grid-cols-3 gap-4">
          {[
            {
              label: 'R-hat max',
              value: results.model_diagnostics.r_hat_max != null ? results.model_diagnostics.r_hat_max.toFixed(3) : 'N/A',
              good: results.model_diagnostics.r_hat_max != null ? results.model_diagnostics.r_hat_max < 1.1 : null,
              hint: '< 1.1 = good convergence',
              tooltip: 'Gelman-Rubin convergence diagnostic. Compares within-chain to between-chain variance. Values close to 1.0 mean all chains converged to the same posterior. Values > 1.1 suggest divergence — increase warmup steps or check the data.',
            },
            {
              label: 'ESS bulk min',
              value: results.model_diagnostics.ess_bulk_min != null ? fmt(results.model_diagnostics.ess_bulk_min) : 'N/A',
              good: results.model_diagnostics.ess_bulk_min != null ? results.model_diagnostics.ess_bulk_min > 400 : null,
              hint: '> 400 = sufficient samples',
              tooltip: 'Effective Sample Size for the bulk of the posterior distribution. Accounts for autocorrelation between MCMC draws. Low ESS (< 400) means the sampler is exploring slowly — increase n_samples or reduce model complexity.',
            },
            {
              label: 'WAIC',
              value: results.model_diagnostics.waic != null ? results.model_diagnostics.waic.toFixed(1) : 'N/A',
              good: null,
              hint: 'Lower is better',
              tooltip: 'Widely Applicable Information Criterion — a Bayesian measure of out-of-sample predictive accuracy, penalised for model complexity. Use this to compare different channel configurations or prior settings for the same dataset. Lower values indicate better predictive performance.',
            },
          ].map(({ label, value, good, hint, tooltip }) => (
            <div key={label} className="rounded-lg border border-gray-200 bg-white px-4 py-3">
              <p className="flex items-center text-xs text-gray-500">
                {label}
                <MetricTooltip text={tooltip} />
              </p>
              <p className={`mt-1 text-lg font-bold ${good === true ? 'text-green-600' : good === false ? 'text-amber-600' : 'text-gray-800'}`}>
                {value}
              </p>
              <p className="text-xs text-gray-400">{hint}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function ExportButton({ results }: { results: RunResults }) {
  function handleExport() {
    const rows: string[] = [
      ['channel', 'prior_spend', 'prior_share_pct', 'optimised_spend', 'optimised_share_pct', 'change'].join(','),
    ]
    const totalPrior = Object.values(results.prior_allocation).reduce((a, b) => a + b, 0)
    const totalOpt = Object.values(results.optimized_allocation).reduce((a, b) => a + b, 0)
    for (const ch of results.channels) {
      const prior = results.prior_allocation[ch] ?? 0
      const opt = results.optimized_allocation[ch] ?? 0
      rows.push([
        ch,
        prior.toFixed(2),
        totalPrior > 0 ? ((prior / totalPrior) * 100).toFixed(2) : '0',
        opt.toFixed(2),
        totalOpt > 0 ? ((opt / totalOpt) * 100).toFixed(2) : '0',
        (opt - prior).toFixed(2),
      ].join(','))
    }
    const blob = new Blob([rows.join('\n')], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${results.run_label.replace(/\s+/g, '_')}_allocation.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <button
      onClick={handleExport}
      className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50 transition-colors"
    >
      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
      </svg>
      Export CSV
    </button>
  )
}
