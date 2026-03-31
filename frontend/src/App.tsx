import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { useSession } from '@/hooks/useSession'
import { useSessionStore } from '@/store/sessionStore'
import { RunsSidebar } from '@/components/runs/RunsSidebar'
import { ErrorBoundary } from '@/components/common/ErrorBoundary'
import { HomePage } from '@/pages/HomePage'
import { RunPage } from '@/pages/RunPage'
import { NewRunPage } from '@/pages/NewRunPage'

function SessionGate({ children }: { children: React.ReactNode }) {
  const { ready, error } = useSession()
  const serverExpired = useSessionStore((s) => s.serverExpired)

  // Server-side TTL expiry: session was purged from Redis while the tab was open.
  // Reloading triggers useSession to create a fresh session automatically.
  if (serverExpired) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 text-center max-w-md">
          <p className="font-semibold text-amber-800">Your session has expired</p>
          <p className="mt-1 text-sm text-amber-600">
            Sessions last 4 hours. Your data has been cleared — start a new run to continue.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 rounded bg-amber-600 px-4 py-2 text-sm text-white hover:bg-amber-700"
          >
            Start fresh
          </button>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center max-w-md">
          <p className="font-semibold text-red-700">Could not connect to the server</p>
          <p className="mt-1 text-sm text-red-500">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 rounded bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  if (!ready) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-center">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-brand-500 border-t-transparent" />
          <p className="mt-3 text-sm text-gray-500">Starting session…</p>
        </div>
      </div>
    )
  }

  return <>{children}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <SessionGate>
        <div className="flex h-screen overflow-hidden">
          {/* Left sidebar — persistent across pages */}
          <RunsSidebar />

          {/* Main content area */}
          <main className="flex-1 overflow-y-auto">
            <ErrorBoundary>
              <Routes>
                <Route path="/" element={<HomePage />} />
                <Route path="/new" element={<NewRunPage />} />
                <Route path="/runs/:runId" element={<RunPage />} />
              </Routes>
            </ErrorBoundary>
          </main>
        </div>
      </SessionGate>
    </BrowserRouter>
  )
}
