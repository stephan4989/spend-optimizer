export interface WeeksRange {
  start: string
  end: string
}

export interface UploadResponse {
  upload_id: string
  filename: string
  rows: number
  weeks_range: WeeksRange
  channels: string[]
  channel_count: number
  total_spend_per_channel: Record<string, number>
}
