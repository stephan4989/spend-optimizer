import { useRef, useState } from 'react'

interface Props {
  onFile: (file: File) => void
  accept?: string
  disabled?: boolean
}

export function FileDropzone({ onFile, accept = '.csv', disabled = false }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragging(false)
    if (disabled) return
    const file = e.dataTransfer.files[0]
    if (file) onFile(file)
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) {
      onFile(file)
      // Reset so the same file can be re-selected if the user wants to re-upload
      e.target.value = ''
    }
  }

  return (
    <div
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-8 py-12 text-center transition-colors
        ${dragging ? 'border-brand-500 bg-brand-50' : 'border-gray-300 bg-gray-50 hover:border-brand-400 hover:bg-brand-50'}
        ${disabled ? 'cursor-not-allowed opacity-50' : ''}`}
    >
      <svg className="mb-3 h-10 w-10 text-gray-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
      </svg>
      <p className="text-sm font-medium text-gray-700">Drop your CSV here, or <span className="text-brand-600 underline">browse</span></p>
      <p className="mt-1 text-xs text-gray-400">Columns: week, channel_1 … channel_n, acquisitions · Max 10 MB</p>
      <input ref={inputRef} type="file" accept={accept} className="hidden" onChange={handleChange} disabled={disabled} />
    </div>
  )
}
