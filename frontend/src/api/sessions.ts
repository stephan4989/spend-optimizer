import client from './client'
import type { SessionCreateResponse, SessionMeResponse } from '@/types/session'

export async function createSession(): Promise<SessionCreateResponse> {
  const res = await client.post<SessionCreateResponse>('/sessions')
  return res.data
}

export async function getSessionMe(): Promise<SessionMeResponse> {
  const res = await client.get<SessionMeResponse>('/sessions/me')
  return res.data
}
