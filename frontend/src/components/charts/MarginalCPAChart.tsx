import { useMemo, useState } from 'react'
import Plot from 'react-plotly.js'
import type { RunResults } from '@/types/results'

interface Props {
  results: RunResults
}

const PALETTE = [
  '#2563eb', '#16a34a', '#dc2626', '#d97706', '#7c3aed',
  '#0891b2', '#be185d', '#65a30d', '#ea580c', '#4338ca',
]

export function MarginalCPAChart({ results }: Props) {
  const [activeChannel, setActiveChannel] = useState<string | null>(null)

  const traces = useMemo((): Plotly.Data[] => {
    return results.channels.flatMap((ch, i) => {
      const curve = results.response_curves[ch]
      if (!curve) return []

      const { spend_points: sp, acquisitions: acq } = curve
      const color = PALETTE[i % PALETTE.length]
      const isActive = activeChannel === null || activeChannel === ch
      const opacity = isActive ? 1 : 0.15

      // Marginal CPA: ΔSpend / ΔAcquisitions between consecutive curve points
      // Skip points where ΔAcq ≈ 0 (flat region — marginal CPA → ∞, not useful)
      const mCPA: number[] = []
      const mSpend: number[] = []
      for (let j = 1; j < sp.length; j++) {
        const dSpend = sp[j] - sp[j - 1]
        const dAcq = acq[j] - acq[j - 1]
        if (dAcq > 0.01) {
          mSpend.push(sp[j])
          mCPA.push(dSpend / dAcq)
        }
      }

      if (mSpend.length === 0) return []

      // Prior spend marker
      const priorSpend = results.prior_allocation[ch] ?? 0
      const traces: Plotly.Data[] = [
        {
          x: mSpend,
          y: mCPA,
          type: 'scatter',
          mode: 'lines',
          name: ch,
          line: { color, width: 2 },
          opacity,
          hovertemplate: `<b>${ch}</b><br>Spend: $%{x:,.0f}<br>Marginal CPA: $%{y:,.0f}<extra></extra>`,
        } as Plotly.Data,
      ]

      // Dot at current (prior) spend level
      if (priorSpend > 0 && priorSpend <= mSpend[mSpend.length - 1]) {
        // Interpolate marginal CPA at prior spend
        let mCPAAtPrior: number | null = null
        for (let j = 0; j < mSpend.length - 1; j++) {
          if (priorSpend >= mSpend[j] && priorSpend <= mSpend[j + 1]) {
            const t = (priorSpend - mSpend[j]) / (mSpend[j + 1] - mSpend[j])
            mCPAAtPrior = mCPA[j] + t * (mCPA[j + 1] - mCPA[j])
            break
          }
        }
        if (mCPAAtPrior !== null) {
          traces.push({
            x: [priorSpend],
            y: [mCPAAtPrior],
            type: 'scatter',
            mode: 'markers',
            name: `${ch} (current)`,
            marker: { color, size: 8, symbol: 'circle', line: { color: 'white', width: 2 } },
            opacity,
            showlegend: false,
            hovertemplate: `<b>${ch} — current spend</b><br>Spend: $%{x:,.0f}<br>Marginal CPA: $%{y:,.0f}<extra></extra>`,
          } as Plotly.Data)
        }
      }

      return traces
    })
  }, [results, activeChannel])

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-2">
        <button
          onClick={() => setActiveChannel(null)}
          className={`rounded-full px-3 py-0.5 text-xs font-medium border transition-colors ${
            activeChannel === null
              ? 'bg-gray-900 border-gray-900 text-white'
              : 'bg-white border-gray-300 text-gray-600 hover:border-gray-400'
          }`}
        >
          All
        </button>
        {results.channels.map((ch, i) => (
          <button
            key={ch}
            onClick={() => setActiveChannel(activeChannel === ch ? null : ch)}
            className="rounded-full px-3 py-0.5 text-xs font-medium border transition-colors"
            style={
              activeChannel === ch
                ? { backgroundColor: PALETTE[i % PALETTE.length], borderColor: PALETTE[i % PALETTE.length], color: 'white' }
                : { backgroundColor: 'white', borderColor: '#d1d5db', color: '#4b5563' }
            }
          >
            {ch}
          </button>
        ))}
      </div>

      <Plot
        data={traces}
        layout={{
          autosize: true,
          height: 340,
          margin: { t: 10, r: 20, b: 50, l: 70 },
          xaxis: {
            title: { text: 'Weekly spend ($)', font: { size: 12 } },
            tickformat: ',.0f',
            tickprefix: '$',
            gridcolor: '#f3f4f6',
            zeroline: false,
          },
          yaxis: {
            title: { text: 'Marginal CPA ($)', font: { size: 12 } },
            tickformat: ',.0f',
            tickprefix: '$',
            gridcolor: '#f3f4f6',
            zeroline: false,
          },
          legend: { orientation: 'h', y: -0.18, x: 0, font: { size: 11 } },
          plot_bgcolor: 'white',
          paper_bgcolor: 'white',
          hovermode: 'closest',
        }}
        config={{ displayModeBar: false, responsive: true }}
        style={{ width: '100%' }}
        useResizeHandler
      />
      <p className="text-center text-xs text-gray-400 -mt-2">
        Rising curve = diminishing returns · Dots = current spend level · Lower is more efficient
      </p>
    </div>
  )
}
