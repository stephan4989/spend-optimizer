import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { useSession } from '@/hooks/useSession'
import { RunsSidebar } from '@/components/runs/RunsSidebar'
import { HomePage } from '@/pages/HomePage'
import { RunPage } from '@/pages/RunPage'

function SessionGate({ children }: { children: React.ReactNode }) {
  const { ready, error } = useSession()

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
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/runs/:runId" element={<RunPage />} />
            </Routes>
          </main>
        </div>
      </SessionGate>
    </BrowserRouter>
  )
}
