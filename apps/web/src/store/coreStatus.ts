import { create } from 'zustand'
import { type CoreVersion, fetchCoreVersion } from '../lib/api.ts'

export type CoreStatus =
  | { state: 'checking' }
  | { state: 'online'; core: CoreVersion }
  | { state: 'offline' }

interface CoreStatusStore {
  status: CoreStatus
  /** Ping the core. Never throws: the outcome lands in `status`. */
  check: () => Promise<void>
}

const CHECK_TIMEOUT_MS = 3000

export const useCoreStatus = create<CoreStatusStore>()((set) => ({
  status: { state: 'checking' },
  check: async () => {
    set({ status: { state: 'checking' } })
    try {
      const core = await fetchCoreVersion(AbortSignal.timeout(CHECK_TIMEOUT_MS))
      set({ status: { state: 'online', core } })
    } catch {
      set({ status: { state: 'offline' } })
    }
  },
}))
