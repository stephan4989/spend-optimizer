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

// Surface error detail from the API as a plain Error message
client.interceptors.response.use(
  (res) => res,
  (err) => {
    const detail = err?.response?.data?.detail
    if (detail) {
      return Promise.reject(new Error(typeof detail === 'string' ? detail : JSON.stringify(detail)))
    }
    return Promise.reject(err)
  }
)

export default client
