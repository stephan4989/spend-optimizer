import client from './client'
import type { RunResults } from '@/types/results'

export async function getResults(sessionId: string, runId: string): Promise<RunResults> {
  const res = await client.get<RunResults>(`/sessions/${sessionId}/runs/${runId}/results`)
  return res.data
}
