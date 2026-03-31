import axios from 'axios'
import { useSessionStore } from '@/store/sessionStore'

const client = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

// Attach session token to every request
client.interceptors.request.use((config) => {
  const sessionId = useSessionStore.getState().sessionId
  if (sessionId) {
    config.headers['X-Session-ID'] = sessionId
  }
  return config
})

// Surface error detail from the API as a plain Error message.
// Also detect server-side session expiry (404 "Session not found or expired.")
// and mark it in the store so the UI can prompt re-initialisation.
client.interceptors.response.use(
  (res) => res,
  (err) => {
    const detail = err?.response?.data?.detail
    if (
      err?.response?.status === 404 &&
      typeof detail === 'string' &&
      detail.toLowerCase().includes('session not found')
    ) {
      useSessionStore.getState().markServerExpired()
    }
    if (detail) {
      return Promise.reject(new Error(typeof detail === 'string' ? detail : JSON.stringify(detail)))
    }
    return Promise.reject(err)
  }
)

export default client
