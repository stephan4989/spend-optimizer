import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface SessionState {
  sessionId: string | null
  expiresAt: string | null
  serverExpired: boolean
  setSession: (sessionId: string, expiresAt: string) => void
  clearSession: () => void
  markServerExpired: () => void
  isExpired: () => boolean
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set, get) => ({
      sessionId: null,
      expiresAt: null,
      serverExpired: false,

      setSession: (sessionId, expiresAt) => set({ sessionId, expiresAt, serverExpired: false }),

      clearSession: () => set({ sessionId: null, expiresAt: null, serverExpired: false }),

      markServerExpired: () => set({ sessionId: null, expiresAt: null, serverExpired: true }),

      isExpired: () => {
        const { expiresAt } = get()
        if (!expiresAt) return true
        return new Date(expiresAt) < new Date()
      },
    }),
    {
      name: 'spend-optimizer-session',
      // Only persist the token + expiry, not transient flags or methods
      partialize: (state) => ({
        sessionId: state.sessionId,
        expiresAt: state.expiresAt,
      }),
    }
  )
)
