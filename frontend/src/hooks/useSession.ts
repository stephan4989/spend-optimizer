import { useEffect, useState } from 'react'
import { createSession } from '@/api/sessions'
import { useSessionStore } from '@/store/sessionStore'

/**
 * Initialises or restores the anonymous session.
 *
 * On mount:
 *  1. Read session token + expiry from localStorage (via Zustand persist).
 *  2. If missing or expired → call POST /sessions to get a new one.
 *  3. Store the result back in the Zustand store (and localStorage).
 *
 * Returns { ready, error } so the app can gate rendering behind session init.
 */
export function useSession() {
  const { sessionId, expiresAt, setSession, clearSession, isExpired } = useSessionStore()
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function init() {
      try {
        if (sessionId && expiresAt && !isExpired()) {
          setReady(true)
          return
        }
        // Session missing or expired — create a new one
        clearSession()
        const session = await createSession()
        setSession(session.session_id, session.expires_at)
        setReady(true)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to initialise session.')
      }
    }
    init()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { ready, error, sessionId }
}
