import { useMemo } from 'react'
import Plot from 'react-plotly.js'
import type { ModelFitData } from '@/types/results'

interface Props {
  data: ModelFitData
}

export function ModelFitChart({ data }: Props) {
  const traces = useMemo((): Plotly.Data[] => {
    // CI band (filled area between upper and lower)
    const ciBand: Plotly.Data = {
      x: [...data.dates, ...data.dates.slice().reverse()],
      y: [...data.predicted_upper, ...data.predicted_lower.slice().reverse()],
      fill: 'toself',
      fillcolor: 'rgba(99,102,241,0.12)',
      line: { width: 0 },
      hoverinfo: 'skip',
      showlegend: true,
      name: '80% CI',
      type: 'scatter',
    }

    const predicted: Plotly.Data = {
      x: data.dates,
      y: data.predicted_mean,
      type: 'scatter',
      mode: 'lines',
      name: 'Predicted',
      line: { color: '#6366f1', width: 2, dash: 'dot' },
      hovertemplate: '<b>Predicted</b><br>%{x}<br>%{y:,.0f}<extra></extra>',
    }

    const actual: Plotly.Data = {
      x: data.dates,
      y: data.actual,
      type: 'scatter',
      mode: 'lines',
      name: 'Actual',
      line: { color: '#111827', width: 2 },
      hovertemplate: '<b>Actual</b><br>%{x}<br>%{y:,.0f}<extra></extra>',
    }

    return [ciBand, predicted, actual]
  }, [data])

  return (
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
          title: { text: 'Acquisitions', font: { size: 12 } },
          tickformat: ',.0f',
          gridcolor: '#f3f4f6',
          zeroline: false,
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
  )
}
