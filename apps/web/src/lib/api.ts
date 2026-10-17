/** Where regista-core listens; set VITE_API_BASE in the repo-root .env. */
export const API_BASE = (import.meta.env.VITE_API_BASE ?? 'http://localhost:8000').replace(/\/+$/, '')

/** Runtime switches reported by the core (offline = memory / template / off / local). */
export interface RuntimeModes {
  bus: string
  llm_mode: string
  tts_mode: string
  store: string
}

/** Payload of `GET /api/version`. */
export interface CoreVersion {
  name: string
  version: string
  modes: RuntimeModes
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null

const isString = (value: unknown): value is string => typeof value === 'string'

/** Validate an untrusted `/api/version` payload; throws when the shape is wrong. */
export function parseCoreVersion(payload: unknown): CoreVersion {
  if (!isRecord(payload) || !isString(payload.name) || !isString(payload.version)) {
    throw new Error('unexpected /api/version payload')
  }
  const modes = payload.modes
  if (
    !isRecord(modes) ||
    !isString(modes.bus) ||
    !isString(modes.llm_mode) ||
    !isString(modes.tts_mode) ||
    !isString(modes.store)
  ) {
    throw new Error('unexpected runtime modes in /api/version')
  }
  return {
    name: payload.name,
    version: payload.version,
    modes: { bus: modes.bus, llm_mode: modes.llm_mode, tts_mode: modes.tts_mode, store: modes.store },
  }
}

/** Ask regista-core what is running. Rejects when the core is unreachable or misbehaves. */
export async function fetchCoreVersion(signal?: AbortSignal): Promise<CoreVersion> {
  const response = await fetch(`${API_BASE}/api/version`, { signal })
  if (!response.ok) throw new Error(`/api/version answered ${response.status}`)
  return parseCoreVersion(await response.json())
}
