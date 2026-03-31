import { useParams } from 'react-router-dom'
import { WizardShell } from '@/components/wizard/WizardShell'

export function RunPage() {
  const { runId } = useParams<{ runId: string }>()

  if (!runId) return null

  return <WizardShell runId={runId} />
}
