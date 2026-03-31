export interface SessionCreateResponse {
  session_id: string
  created_at: string
  expires_at: string
  ttl_seconds: number
}

export interface SessionMeResponse {
  session_id: string
  created_at: string
  expires_at: string
  ttl_seconds: number
  run_count: number
}
