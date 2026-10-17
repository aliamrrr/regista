interface ImportMetaEnv {
  /** Base URL of regista-core's REST API, from the repo-root .env (see .env.example). */
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
