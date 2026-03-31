import Plot from 'react-plotly.js'
import type { RunResults } from '@/types/results'

interface Props {
  results: RunResults
}

export function BudgetAllocationChart({ results }: Props) {
  const channels = results.channels
  const prior = channels.map((ch) => results.prior_allocation[ch] ?? 0)
  const optimized = channels.map((ch) => results.optimized_allocation[ch] ?? 0)

  const traces: Plotly.Data[] = [
    {
      type: 'bar',
      name: 'Prior',
      x: channels,
      y: prior,
      marker: { color: '#94a3b8' },
      hovertemplate: '<b>%{x}</b><br>Prior: $%{y:,.0f}<extra></extra>',
    } as Plotly.Data,
    {
      type: 'bar',
      name: 'Optimised',
      x: channels,
      y: optimized,
      marker: { color: '#2563eb' },
      hovertemplate: '<b>%{x}</b><br>Optimised: $%{y:,.0f}<extra></extra>',
    } as Plotly.Data,
  ]

  return (
    <Plot
      data={traces}
      layout={{
        autosize: true,
        height: 300,
        barmode: 'group',
        margin: { t: 10, r: 20, b: 60, l: 60 },
        xaxis: {
          tickfont: { size: 11 },
          gridcolor: '#f3f4f6',
        },
        yaxis: {
          title: { text: 'Spend ($)', font: { size: 12 } },
          tickformat: ',.0f',
          tickprefix: '$',
          gridcolor: '#f3f4f6',
          zeroline: false,
        },
        legend: {
          orientation: 'h',
          y: -0.22,
          x: 0.5,
          xanchor: 'center',
          font: { size: 11 },
        },
        plot_bgcolor: 'white',
        paper_bgcolor: 'white',
        bargap: 0.25,
        bargroupgap: 0.08,
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: '100%' }}
      useResizeHandler
    />
  )
}
