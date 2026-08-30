/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_ADK_APP_NAME?: string
  readonly VITE_GRAFANA_URL?: string
  readonly VITE_ARGOCD_URL?: string
  readonly VITE_GITHUB_URL?: string
  readonly VITE_ENVIRONMENT?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
