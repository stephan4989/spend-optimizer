import { useState } from 'react'
import Papa from 'papaparse'
import { uploadCSV } from '@/api/uploads'
import { useSessionStore } from '@/store/sessionStore'
import type { UploadResponse } from '@/types/upload'
import { FileDropzone } from '@/components/common/FileDropzone'
import { DataTable } from '@/components/common/DataTable'
import { ErrorBanner } from '@/components/common/ErrorBanner'

interface Props {
  onComplete: (upload: UploadResponse) => void
}

interface ParsedPreview {
  headers: string[]
  rows: string[][]
  totalRows: number
  channels: string[]
  validationError: string | null
}

function validateAndPreview(_file: File, text: string): ParsedPreview {
  const result = Papa.parse<Record<string, string>>(text, {
    header: true,
    skipEmptyLines: true,
  })

  const headers = result.meta.fields ?? []
  const rows = result.data.map((row) => headers.map((h) => row[h] ?? ''))
  const totalRows = rows.length

  const DATE_ALIASES = ['date', 'week', 'month']
  const KPI_ALIASES = ['acquisitions', 'sales', 'revenue', 'conversions', 'orders', 'leads', 'purchases', 'transactions', 'signups', 'installs']
  const dateCol = DATE_ALIASES.find((c) => headers.map(h => h.toLowerCase()).includes(c))
  const kpiCol = KPI_ALIASES.find((c) => headers.map(h => h.toLowerCase()).includes(c))
  if (!dateCol || !kpiCol) {
    const missing = []
    if (!dateCol) missing.push("'date', 'week', or 'month'")
    if (!kpiCol) missing.push("'acquisitions' (or: sales, revenue, conversions, orders)")
    return { headers, rows, totalRows, channels: [], validationError: `Missing required column(s): ${missing.join(', ')}` }
  }

  const reserved = new Set([...DATE_ALIASES, ...KPI_ALIASES])
  const channels = headers.filter((h) => !reserved.has(h.toLowerCase()))
  if (channels.length === 0) {
    return { headers, rows, totalRows, channels, validationError: 'No channel columns found. Add at least one spend column.' }
  }
  if (channels.length > 10) {
    return { headers, rows, totalRows, channels, validationError: `Too many channels (${channels.length}). Maximum is 10.` }
  }
  if (totalRows < 6) {
    return { headers, rows, totalRows, channels, validationError: `Not enough data rows (${totalRows}). Minimum is 6 rows.` }
  }

  return { headers, rows, totalRows, channels, validationError: null }
}

export function StepUpload({ onComplete }: Props) {
  const sessionId = useSessionStore((s) => s.sessionId)!
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<ParsedPreview | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function handleFile(f: File) {
    setError(null)
    setFile(f)
    const reader = new FileReader()
    reader.onload = (e) => {
      const text = e.target?.result as string
      setPreview(validateAndPreview(f, text))
    }
    reader.readAsText(f)
  }

  async function handleUpload() {
    if (!file || !preview || preview.validationError) return
    setUploading(true)
    setError(null)
    try {
      const response = await uploadCSV(sessionId, file)
      onComplete(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-8 py-10">
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-gray-900">Upload spend data</h2>
        <p className="mt-1 text-sm text-gray-500">
          Upload a CSV with weekly spend per channel and total acquisitions.
        </p>
      </div>

      <FileDropzone onFile={handleFile} disabled={uploading} />

      {error && (
        <div className="mt-4">
          <ErrorBanner message={error} onDismiss={() => setError(null)} />
        </div>
      )}

      {preview && (
        <div className="mt-6 space-y-4">
          {/* File summary */}
          <div className="flex items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-3">
            <div className="flex items-center gap-3">
              <svg className="h-8 w-8 text-green-500" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
              </svg>
              <div>
                <p className="text-sm font-medium text-gray-900">{file?.name}</p>
                <p className="text-xs text-gray-500">{preview.totalRows} rows · {preview.channels.length} channels detected</p>
              </div>
            </div>
            <button onClick={() => { setFile(null); setPreview(null) }} className="text-xs text-gray-400 hover:text-gray-600">
              Change
            </button>
          </div>

          {/* Validation error */}
          {preview.validationError && (
            <ErrorBanner message={preview.validationError} />
          )}

          {/* Detected channels */}
          {!preview.validationError && (
            <div>
              <p className="mb-2 text-xs font-medium text-gray-500 uppercase tracking-wide">Detected channels</p>
              <div className="flex flex-wrap gap-2">
                {preview.channels.map((ch) => (
                  <span key={ch} className="rounded-full bg-brand-100 px-2.5 py-0.5 text-xs font-medium text-brand-700">
                    {ch}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* CSV Preview */}
          <div>
            <p className="mb-2 text-xs font-medium text-gray-500 uppercase tracking-wide">Preview</p>
            <DataTable headers={preview.headers} rows={preview.rows} maxRows={5} />
          </div>

          {/* Continue button */}
          {!preview.validationError && (
            <div className="flex justify-end pt-2">
              <button
                onClick={handleUpload}
                disabled={uploading}
                className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60 transition-colors"
              >
                {uploading ? (
                  <>
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                    Uploading…
                  </>
                ) : (
                  <>
                    Continue
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                    </svg>
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
