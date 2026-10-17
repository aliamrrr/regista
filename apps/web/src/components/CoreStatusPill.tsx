import { useEffect } from 'react'
import { type CoreStatus, useCoreStatus } from '../store/coreStatus.ts'

const DOT: Record<CoreStatus['state'], string> = {
  checking: 'bg-dim animate-live',
  online: 'bg-ok shadow-[0_0_0_4px_var(--ok-a)] animate-live',
  offline: 'bg-alert shadow-[0_0_0_4px_var(--alert-a)]',
}

function StatusText({ status }: { status: CoreStatus }) {
  switch (status.state) {
    case 'checking':
      return <>Connecting to core…</>
    case 'online':
      return (
        <>
          Core v{status.core.version} · {status.core.modes.bus} bus · LLM {status.core.modes.llm_mode}
        </>
      )
    case 'offline':
      return (
        <>
          Core offline · start it with{' '}
          <code className="font-mono text-flood">uv run regista-core serve</code>
        </>
      )
  }
}

/** Live connection pill: shows whether regista-core answers and which modes it runs. */
export function CoreStatusPill() {
  const status = useCoreStatus((store) => store.status)
  const check = useCoreStatus((store) => store.check)

  useEffect(() => {
    void check()
  }, [check])

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* <output> carries the implicit ARIA "status" role: changes are announced politely. */}
      <output
        aria-live="polite"
        className="inline-flex min-h-9 items-center gap-2 rounded-full border border-line-2 bg-ink-3 px-3.5 py-1.5 text-[13px] font-semibold"
      >
        <span aria-hidden="true" className={`size-2 shrink-0 rounded-full ${DOT[status.state]}`} />
        <span>
          <StatusText status={status} />
        </span>
      </output>
      {status.state === 'offline' && (
        <button
          type="button"
          onClick={() => void check()}
          className="h-9 cursor-pointer rounded-full border border-line-2 bg-ink-3 px-3.5 text-[13px] font-semibold hover:border-mist"
        >
          Retry
        </button>
      )}
    </div>
  )
}
