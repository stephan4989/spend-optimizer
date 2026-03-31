export interface ResponseCurveData {
  spend_points: number[]
  acquisitions: number[]
  ci_lower: number[]
  ci_upper: number[]
}

export interface ModelDiagnostics {
  r_hat_max: number
  ess_bulk_min: number
  waic: number | null
}

export interface RunResults {
  run_id: string
  run_label: string
  channels: string[]
  response_curves: Record<string, ResponseCurveData>
  prior_allocation: Record<string, number>
  optimized_allocation: Record<string, number>
  prior_total_acquisitions: number
  optimized_total_acquisitions: number
  lift_pct: number
  model_diagnostics: ModelDiagnostics
}
