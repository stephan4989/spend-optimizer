import client from './client'
import type {
  RunCreateRequest,
  RunCreateResponse,
  RunDetail,
  RunListResponse,
} from '@/types/run'

export async function createRun(
  sessionId: string,
  body: RunCreateRequest
): Promise<RunCreateResponse> {
  const res = await client.post<RunCreateResponse>(`/sessions/${sessionId}/runs`, body)
  return res.data
}

export async function listRuns(sessionId: string): Promise<RunListResponse> {
  const res = await client.get<RunListResponse>(`/sessions/${sessionId}/runs`)
  return res.data
}

export async function getRun(sessionId: string, runId: string): Promise<RunDetail> {
  const res = await client.get<RunDetail>(`/sessions/${sessionId}/runs/${runId}`)
  return res.data
}
