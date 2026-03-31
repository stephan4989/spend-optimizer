import { create } from 'zustand'
import type { RunResults } from '@/types/results'
import type { RunSummary } from '@/types/run'

interface RunsState {
  runs: RunSummary[]
  results: Record<string, RunResults>   // keyed by run_id
  activeRunId: string | null

  setRuns: (runs: RunSummary[]) => void
  upsertRun: (run: RunSummary) => void
  setResults: (runId: string, results: RunResults) => void
  setActiveRunId: (runId: string | null) => void
  clearAll: () => void
}

export const useRunsStore = create<RunsState>((set) => ({
  runs: [],
  results: {},
  activeRunId: null,

  setRuns: (runs) => set({ runs }),

  upsertRun: (run) =>
    set((state) => {
      const idx = state.runs.findIndex((r) => r.run_id === run.run_id)
      if (idx === -1) {
        return { runs: [...state.runs, run] }
      }
      const updated = [...state.runs]
      updated[idx] = run
      return { runs: updated }
    }),

  setResults: (runId, results) =>
    set((state) => ({ results: { ...state.results, [runId]: results } })),

  setActiveRunId: (runId) => set({ activeRunId: runId }),

  clearAll: () => set({ runs: [], results: {}, activeRunId: null }),
}))
