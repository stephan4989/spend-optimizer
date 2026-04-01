import { useMemo, useState } from 'react'
import Plot from 'react-plotly.js'
import type { ContributionData } from '@/types/results'

interface Props {
  data: ContributionData
  channels: string[]
}

const PALETTE = [
  '#2563eb', '#16a34a', '#dc2626', '#d97706', '#7c3aed',
  '#0891b2', '#be185d', '#65a30d', '#ea580c', '#4338ca',
]
const BASELINE_COLOR = '#9ca3af'

export function ContributionChart({ data, channels }: Props) {
  const [showPct, setShowPct] = useState(false)

  // Compute totals per time step for percentage normalisation
  const totals = useMemo(() => {
    return data.dates.map((_, t) => {
      const mediaSum = channels.reduce((s, ch) => s + (data.contributions[ch]?.[t] ?? 0), 0)
      return mediaSum + (data.baseline[t] ?? 0)
    })
  }, [data, channels])

  const traces = useMemo((): Plotly.Data[] => {
    const normalise = (val: number, t: number) =>
      showPct ? (totals[t] > 0 ? (val / totals[t]) * 100 : 0) : val

    const out: Plotly.Data[] = []

    // Baseline first so it sits at the bottom of the stack
    out.push({
      x: data.dates,
      y: data.baseline.map((v, t) => normalise(v, t)),
      type: 'scatter',
      mode: 'lines',
      stackgroup: 'one',
      name: 'Baseline',
      line: { width: 0 },
      fillcolor: BASELINE_COLOR,
      hovertemplate: showPct
        ? '<b>Baseline</b><br>%{x}<br>%{y:.1f}%<extra></extra>'
        : '<b>Baseline</b><br>%{x}<br>%{y:,.0f} acq<extra></extra>',
    } as Plotly.Data)

    // Channels stacked on top
    channels.forEach((ch, i) => {
      const color = PALETTE[i % PALETTE.length]
      out.push({
        x: data.dates,
        y: (data.contributions[ch] ?? []).map((v, t) => normalise(v, t)),
        type: 'scatter',
        mode: 'lines',
        stackgroup: 'one',
        name: ch,
        line: { width: 0 },
        fillcolor: color,
        hovertemplate: showPct
          ? `<b>${ch}</b><br>%{x}<br>%{y:.1f}%<extra></extra>`
          : `<b>${ch}</b><br>%{x}<br>%{y:,.0f} acq<extra></extra>`,
      } as Plotly.Data)
    })

    return out
  }, [data, channels, showPct, totals])

  return (
    <div>
      {/* Toggle */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-1 rounded-lg border border-gray-200 p-0.5 text-xs">
          <button
            onClick={() => setShowPct(false)}
            className={`rounded-md px-3 py-1 font-medium transition-colors ${!showPct ? 'bg-gray-900 text-white' : 'text-gray-500 hover:text-gray-700'}`}
          >
            Absolute
          </button>
          <button
            onClick={() => setShowPct(true)}
            className={`rounded-md px-3 py-1 font-medium transition-colors ${showPct ? 'bg-gray-900 text-white' : 'text-gray-500 hover:text-gray-700'}`}
          >
            % share
          </button>
        </div>
      </div>

      <Plot
        data={traces}
        layout={{
          autosize: true,
          height: 300,
          margin: { t: 10, r: 20, b: 50, l: 60 },
          xaxis: {
            type: 'date',
            tickformat: '%b %Y',
            gridcolor: '#f3f4f6',
            zeroline: false,
          },
          yaxis: {
            title: { text: showPct ? 'Share (%)' : 'Acquisitions attributed', font: { size: 12 } },
            tickformat: showPct ? '.0f' : ',.0f',
            ticksuffix: showPct ? '%' : '',
            gridcolor: '#f3f4f6',
            zeroline: false,
            range: showPct ? [0, 100] : undefined,
          },
          legend: { orientation: 'h', y: -0.2, x: 0, font: { size: 11 } },
          plot_bgcolor: 'white',
          paper_bgcolor: 'white',
          hovermode: 'x unified',
        }}
        config={{ displayModeBar: false, responsive: true }}
        style={{ width: '100%' }}
        useResizeHandler
      />
      <p className="text-center text-xs text-gray-400 -mt-2">
        Baseline = organic, trend &amp; seasonality · Media contributions use time-series adstock
      </p>
    </div>
  )
}
