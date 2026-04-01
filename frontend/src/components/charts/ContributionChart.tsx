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

export function ContributionChart({ data, channels }: Props) {
  const [activeChannel, setActiveChannel] = useState<string | null>(null)

  const traces = useMemo((): Plotly.Data[] => {
    return channels.map((ch, i) => {
      const color = PALETTE[i % PALETTE.length]
      const isActive = activeChannel === null || activeChannel === ch
      return {
        x: data.dates,
        y: data.contributions[ch] ?? [],
        type: 'scatter',
        mode: 'lines',
        stackgroup: 'one',
        name: ch,
        line: { color, width: 0 },
        fillcolor: isActive ? color : `${color}33`,
        opacity: isActive ? 0.85 : 0.25,
        hovertemplate: `<b>${ch}</b><br>%{x}<br>%{y:,.0f} acq<extra></extra>`,
      } as Plotly.Data
    })
  }, [data, channels, activeChannel])

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
        {channels.map((ch, i) => (
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
          height: 300,
          margin: { t: 10, r: 20, b: 50, l: 60 },
          xaxis: {
            type: 'date',
            tickformat: '%b %Y',
            gridcolor: '#f3f4f6',
            zeroline: false,
          },
          yaxis: {
            title: { text: 'Acquisitions attributed', font: { size: 12 } },
            tickformat: ',.0f',
            gridcolor: '#f3f4f6',
            zeroline: false,
          },
          legend: { orientation: 'h', y: -0.2, x: 0, font: { size: 11 } },
          plot_bgcolor: 'white',
          paper_bgcolor: 'white',
          hovermode: 'x unified',
          barmode: 'stack',
        }}
        config={{ displayModeBar: false, responsive: true }}
        style={{ width: '100%' }}
        useResizeHandler
      />
      <p className="text-center text-xs text-gray-400 -mt-2">
        Media-attributed acquisitions only · baseline (organic + trend) excluded
      </p>
    </div>
  )
}
