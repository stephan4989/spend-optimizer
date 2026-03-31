import { useNavigate } from 'react-router-dom'

export function HomePage() {
  const navigate = useNavigate()

  return (
    <div className="flex h-full flex-col items-center justify-center px-8 py-16 text-center">
      <div className="max-w-md">
        {/* Icon */}
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-100">
          <svg className="h-8 w-8 text-brand-600" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
          </svg>
        </div>

        <h2 className="text-2xl font-bold text-gray-900">Marketing Mix Optimisation</h2>
        <p className="mt-3 text-gray-500">
          Upload your weekly spend data, run a Media Mix Model, and discover how to reallocate
          your budget for maximum acquisitions.
        </p>

        <button
          onClick={() => navigate('/new')}
          className="mt-8 inline-flex items-center gap-2 rounded-lg bg-brand-600 px-6 py-3 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 transition-colors"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          Start New Model Run
        </button>

        {/* How it works */}
        <div className="mt-12 grid grid-cols-3 gap-4 text-left">
          {[
            { step: '1', title: 'Upload', desc: 'Upload a CSV with weekly spend per channel and total acquisitions.' },
            { step: '2', title: 'Configure', desc: 'Set your optimisation budget and any per-channel constraints.' },
            { step: '3', title: 'Optimise', desc: 'The model runs and returns response curves and an optimal allocation.' },
          ].map(({ step, title, desc }) => (
            <div key={step} className="rounded-lg border border-gray-200 bg-white p-4">
              <div className="mb-2 flex h-7 w-7 items-center justify-center rounded-full bg-brand-100 text-xs font-bold text-brand-700">
                {step}
              </div>
              <p className="text-sm font-semibold text-gray-800">{title}</p>
              <p className="mt-1 text-xs text-gray-500">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
