import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { API_BASE, type CoreVersion } from '../lib/api.ts'
import { useCoreStatus } from '../store/coreStatus.ts'
import { App } from './App.tsx'

const OFFLINE_CORE: CoreVersion = {
  name: 'regista-core',
  version: '0.1.0',
  modes: { bus: 'memory', llm_mode: 'template', tts_mode: 'off', store: 'local' },
}

describe('App (Phase 0 placeholder)', () => {
  beforeEach(() => {
    useCoreStatus.setState({ status: { state: 'checking' } })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the brand, the pitch and an RTL Arabic tile, and reports a missing core', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockRejectedValue(new TypeError('Failed to fetch')))

    render(<App />)

    expect(screen.getByText('REGISTA')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Every fan gets their own broadcast.',
    )
    const arabic = screen.getByText('مباراة واحدة. لكل مشجع بثّه الخاص.').closest('article')
    expect(arabic).toHaveAttribute('dir', 'rtl')
    expect(arabic).toHaveAttribute('lang', 'ar')
    expect(await screen.findByText(/core offline/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })

  it('shows the core version and runtime modes when regista-core answers', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(Response.json(OFFLINE_CORE))
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)

    expect(await screen.findByText(/core v0\.1\.0/i)).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('memory bus · LLM template')
    // API_BASE, not a literal URL: Vitest reads the developer's repo-root .env.
    expect(fetchMock).toHaveBeenCalledWith(`${API_BASE}/api/version`, expect.anything())
  })
})
