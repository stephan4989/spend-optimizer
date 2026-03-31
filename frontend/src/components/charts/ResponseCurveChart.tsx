import { useMemo, useState } from 'react'
import Plot from 'react-plotly.js'
import type { RunResults } from '@/types/results'

interface Props {
  results: RunResults
}

// 10-color palette that looks good on white
const PALETTE = [
  '#2563eb', '#16a34a', '#dc2626', '#d97706', '#7c3aed',
  '#0891b2', '#be185d', '#65a30d', '#ea580c', '#4338ca',
]

export function ResponseCurveChart({ results }: Props) {
  const [activeChannel, setActiveChannel] = useState<string | null>(null)

  const traces = useMemo(() => {
    const out: Plotly.Data[] = []

    results.channels.forEach((ch, i) => {
      const curve = results.response_curves[ch]
      if (!curve) return
      const color = PALETTE[i % PALETTE.length]
      const isActive = activeChannel === null || activeChannel === ch
      const opacity = isActive ? 1 : 0.15

      // CI shading (filled area between upper and lower)
      out.push({
        x: [...curve.spend_points, ...curve.spend_points.slice().reverse()],
        y: [...curve.ci_upper, ...curve.ci_lower.slice().reverse()],
        fill: 'toself',
        fillcolor: color,
        line: { width: 0 },
        opacity: isActive ? 0.15 : 0.04,
        hoverinfo: 'skip',
        showlegend: false,
        name: ch,
        type: 'scatter',
      } as Plotly.Data)

      // Mean line
      out.push({
        x: curve.spend_points,
        y: curve.acquisitions,
        type: 'scatter',
        mode: 'lines',
        name: ch,
        line: { color, width: 2 },
        opacity,
        hovertemplate: `<b>${ch}</b><br>Spend: $%{x:,.0f}<br>Acquisitions: %{y:,.0f}<extra></extra>`,
      } as Plotly.Data)

      // Dot for prior allocation
      const priorSpend = results.prior_allocation[ch] ?? 0
      if (priorSpend > 0 && curve.spend_points.length > 0) {
        // Interpolate acquisitions at priorSpend
        const pts = curve.spend_points
        const acqs = curve.acquisitions
        let priorAcq = acqs[0]
        for (let j = 0; j < pts.length - 1; j++) {
          if (priorSpend >= pts[j] && priorSpend <= pts[j + 1]) {
            const t = (priorSpend - pts[j]) / (pts[j + 1] - pts[j])
            priorAcq = acqs[j] + t * (acqs[j + 1] - acqs[j])
            break
          }
        }
        out.push({
          x: [priorSpend],
          y: [priorAcq],
          type: 'scatter',
          mode: 'markers',
          name: `${ch} (prior)`,
          marker: { color, size: 8, symbol: 'circle', line: { color: 'white', width: 2 } },
          opacity,
          showlegend: false,
          hovertemplate: `<b>${ch} — prior</b><br>Spend: $%{x:,.0f}<br>Acquisitions: %{y:,.0f}<extra></extra>`,
        } as Plotly.Data)
      }
    })

    return out
  }, [results, activeChannel])

  return (
    <div>
      {/* Channel filter chips */}
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
            className={`rounded-full px-3 py-0.5 text-xs font-medium border transition-colors`}
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
          margin: { t: 10, r: 20, b: 50, l: 60 },
          xaxis: {
            title: { text: 'Weekly spend ($)', font: { size: 12 } },
            tickformat: ',.0f',
            tickprefix: '$',
            gridcolor: '#f3f4f6',
            zeroline: false,
          },
          yaxis: {
            title: { text: 'Acquisitions', font: { size: 12 } },
            tickformat: ',.0f',
            gridcolor: '#f3f4f6',
            zeroline: false,
          },
          legend: {
            orientation: 'h',
            y: -0.18,
            x: 0,
            font: { size: 11 },
          },
          plot_bgcolor: 'white',
          paper_bgcolor: 'white',
          hovermode: 'closest',
        }}
        config={{ displayModeBar: false, responsive: true }}
        style={{ width: '100%' }}
        useResizeHandler
      />
      <p className="text-center text-xs text-gray-400 -mt-2">
        Shaded bands = 80% credible interval · Dots = current (prior) spend
      </p>
    </div>
  )
}
