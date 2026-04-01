export interface DateRange {
  start: string
  end: string
}

export interface UploadResponse {
  upload_id: string
  filename: string
  rows: number
  date_range: DateRange
  granularity: 'daily' | 'weekly' | 'monthly'
  channels: string[]
  channel_count: number
  total_spend_per_channel: Record<string, number>
  column_renames: Record<string, string>  // original → normalised, empty if no remapping
  sparse_channels: string[]               // channels with >70% zeros, pre-excluded by default
}
