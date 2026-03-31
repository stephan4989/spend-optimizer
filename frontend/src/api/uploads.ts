import client from './client'
import type { UploadResponse } from '@/types/upload'

export async function uploadCSV(sessionId: string, file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  const res = await client.post<UploadResponse>(
    `/sessions/${sessionId}/uploads`,
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  )
  return res.data
}
