import { useEffect, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { listRuns } from '@/api/runs'
import { getResults } from '@/api/results'
import { useSessionStore } from '@/store/sessionStore'
import { useRunsStore } from '@/store/runsStore'
import { RunStatusBadge } from './RunStatusBadge'
import { TERMINAL_STATUSES } from '@/types/run'

const POLL_INTERVAL_MS = 4000

export function RunsSidebar() {
  const sessionId = useSessionStore((s) => s.sessionId)
  const { runs, setRuns, upsertRun, setResults, setActiveRunId } = useRunsStore()
  const navigate = useNavigate()
  const { runId: activeRunId } = useParams<{ runId: string }>()
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!sessionId) return

    const refresh = async () => {
      try {
        const res = await listRuns(sessionId)
        setRuns(res.runs)

        // Fetch results for any newly-completed runs not yet in the store
        for (const run of res.runs) {
          if (run.status === 'completed') {
            const { results } = useRunsStore.getState()
            if (!results[run.run_id]) {
              try {
                const r = await getResults(sessionId, run.run_id)
                setResults(run.run_id, r)
              } catch {/* ignore */}
            }
          }
        }
      } catch {/* ignore network hiccups */}
    }

    // Always poll on a fixed interval — never stop, so new runs are picked up
    // immediately without needing a page reload or session change.
    refresh()
    intervalRef.current = setInterval(refresh, POLL_INTERVAL_MS)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  function handleNewRun() {
    setActiveRunId(null)
    navigate('/new')
  }

  function handleSelectRun(runId: string) {
    setActiveRunId(runId)
    navigate(`/runs/${runId}`)
  }

  return (
    <aside className="flex w-64 flex-col border-r border-gray-200 bg-white">
      {/* Header */}
      <div className="border-b border-gray-200 px-4 py-4">
        <h1 className="text-base font-semibold text-gray-900">Spend Optimizer</h1>
        <p className="mt-0.5 text-xs text-gray-500">Media Mix Modelling</p>
      </div>

      {/* New Run button */}
      <div className="px-3 pt-3">
        <button
          onClick={handleNewRun}
          className="flex w-full items-center justify-center gap-2 rounded-md bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700 transition-colors"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          New Model Run
        </button>
      </div>

      {/* Run list */}
      <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-1 scrollbar-thin">
        {runs.length === 0 && (
          <p className="px-1 py-2 text-xs text-gray-400">
            No runs yet. Click "New Model Run" to get started.
          </p>
        )}
        {runs.map((run) => (
          <button
            key={run.run_id}
            onClick={() => handleSelectRun(run.run_id)}
            className={`w-full rounded-md px-3 py-2.5 text-left transition-colors ${
              run.run_id === activeRunId
                ? 'bg-brand-50 text-brand-700'
                : 'text-gray-700 hover:bg-gray-100'
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <span className="truncate text-sm font-medium">{run.run_label}</span>
            </div>
            <div className="mt-1">
              <RunStatusBadge status={run.status} />
            </div>
            {run.status === 'fitting' || run.status === 'optimizing' ? (
              <div className="mt-1.5 h-1 w-full rounded-full bg-gray-100 overflow-hidden">
                <div
                  className="h-full rounded-full bg-brand-500 transition-all duration-500"
                  style={{ width: `${run.progress_pct}%` }}
                />
              </div>
            ) : null}
          </button>
        ))}
      </nav>

      {/* Session info footer */}
      <div className="border-t border-gray-200 px-4 py-3 space-y-2">
        <p className="text-xs text-gray-400">Session expires in ~4 hrs</p>
        <p className="text-xs text-gray-400">Data is not stored permanently.</p>
        <button
          onClick={() => {
            useSessionStore.getState().clearSession()
            window.location.reload()
          }}
          className="text-xs text-gray-400 underline hover:text-gray-600 transition-colors"
        >
          Reset session
        </button>
      </div>
    </aside>
  )
}
