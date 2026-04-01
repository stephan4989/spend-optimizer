export type RunStatus = 'queued' | 'fitting' | 'optimizing' | 'completed' | 'failed'

export interface ChannelConstraint {
  min_fraction: number
  max_fraction: number
}

export interface MeridianConfig {
  n_chains: number
  n_warmup: number
  n_samples: number
  enable_aks: boolean
  roi_mu: number | null
  roi_sigma: number | null
}

export interface RunCreateRequest {
  upload_id: string
  run_label: string
  total_budget: number            // per-period budget
  planning_period_label: string
  n_periods: number
  channel_names?: string[]
  channel_constraints: Record<string, ChannelConstraint>
  meridian_config: MeridianConfig
}

export interface RunSummary {
  run_id: string
  run_label: string
  status: RunStatus
  created_at: string
  completed_at: string | null
  progress_pct: number
  error_message: string | null
}

export interface RunDetail extends RunSummary {
  session_id: string
  celery_task_id: string | null
}

export interface RunCreateResponse {
  run_id: string
  session_id: string
  run_label: string
  status: RunStatus
  created_at: string
  celery_task_id: string | null
}

export interface RunListResponse {
  runs: RunSummary[]
}

export const DEFAULT_MERIDIAN_CONFIG: MeridianConfig = {
  n_chains: 1,
  n_warmup: 500,
  n_samples: 100,
  enable_aks: false,
  roi_mu: null,
  roi_sigma: null,
}

export const TERMINAL_STATUSES: RunStatus[] = ['completed', 'failed']
