import client from './client'
import type { RunResults, ScenarioResult } from '@/types/results'

export async function getResults(sessionId: string, runId: string): Promise<RunResults> {
  const res = await client.get<RunResults>(`/sessions/${sessionId}/runs/${runId}/results`)
  return res.data
}

export async function optimiseScenario(
  sessionId: string,
  runId: string,
  totalBudget: number,
): Promise<ScenarioResult> {
  const res = await client.post<ScenarioResult>(
    `/sessions/${sessionId}/runs/${runId}/optimise`,
    { total_budget: totalBudget, channel_constraints: {} },
  )
  return res.data
}
