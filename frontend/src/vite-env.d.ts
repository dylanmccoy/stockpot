/// <reference types="vite/client" />

interface ImportMetaEnv {
  /**
   * Build-time flag. When set (any non-empty value), the Login screen also
   * renders the registration form for first-user bootstrap. The default
   * production bundle leaves it unset — no signup UI (docs/frontend/spec.md §4).
   */
  readonly VITE_ENABLE_REGISTER?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
