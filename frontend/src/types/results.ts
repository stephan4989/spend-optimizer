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

export interface ModelFitData {
  dates: string[]
  actual: number[]
  predicted_mean: number[]
  predicted_lower: number[]
  predicted_upper: number[]
}

export interface ContributionData {
  dates: string[]
  contributions: Record<string, number[]>
}

export interface ScenarioResult {
  total_budget: number
  optimized_allocation: Record<string, number>
  optimized_total_acquisitions: number
  prior_total_acquisitions: number
  lift_pct: number
}

export interface RunResults {
  run_id: string
  run_label: string
  channels: string[]
  response_curves: Record<string, ResponseCurveData>
  prior_allocation: Record<string, number>       // per-period spend
  optimized_allocation: Record<string, number>   // per-period spend
  prior_total_acquisitions: number
  optimized_total_acquisitions: number
  lift_pct: number
  model_diagnostics: ModelDiagnostics
  planning_period_label: string
  n_periods: number
  model_fit: ModelFitData | null
  contributions: ContributionData | null
}
