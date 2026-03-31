import { useEffect, useRef } from 'react'
import { getRun } from '@/api/runs'
import { getResults } from '@/api/results'
import { useSessionStore } from '@/store/sessionStore'
import { useRunsStore } from '@/store/runsStore'
import { TERMINAL_STATUSES } from '@/types/run'

const POLL_INTERVAL_MS = 3000

/**
 * Polls GET /runs/{runId} every 3 seconds while the run is in a non-terminal state.
 *
 * On completion, also fetches results and stores them in runsStore.
 * Clears the interval on unmount or once a terminal state is reached.
 */
export function useRunPolling(runId: string | null) {
  const sessionId = useSessionStore((s) => s.sessionId)
  const { upsertRun, setResults } = useRunsStore()
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!runId || !sessionId) return

    const poll = async () => {
      try {
        const run = await getRun(sessionId, runId)
        upsertRun(run)

        if (TERMINAL_STATUSES.includes(run.status)) {
          if (intervalRef.current) {
            clearInterval(intervalRef.current)
            intervalRef.current = null
          }
          if (run.status === 'completed') {
            const results = await getResults(sessionId, runId)
            setResults(runId, results)
          }
        }
      } catch {
        // Network hiccup — keep polling; the run will eventually complete or fail
      }
    }

    // Poll immediately, then on interval
    poll()
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [runId, sessionId, upsertRun, setResults])
}
