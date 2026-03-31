import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface SessionState {
  sessionId: string | null
  expiresAt: string | null
  setSession: (sessionId: string, expiresAt: string) => void
  clearSession: () => void
  isExpired: () => boolean
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set, get) => ({
      sessionId: null,
      expiresAt: null,

      setSession: (sessionId, expiresAt) => set({ sessionId, expiresAt }),

      clearSession: () => set({ sessionId: null, expiresAt: null }),

      isExpired: () => {
        const { expiresAt } = get()
        if (!expiresAt) return true
        return new Date(expiresAt) < new Date()
      },
    }),
    {
      name: 'spend-optimizer-session',
      // Only persist the token + expiry, not the methods
      partialize: (state) => ({
        sessionId: state.sessionId,
        expiresAt: state.expiresAt,
      }),
    }
  )
)
