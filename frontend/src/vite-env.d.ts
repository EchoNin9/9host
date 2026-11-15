/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_COGNITO_USER_POOL_ID?: string;
  readonly VITE_COGNITO_CLIENT_ID?: string;
  readonly VITE_COGNITO_REGION?: string;
  readonly VITE_ENABLE_BILLING?: string;
  readonly VITE_ENABLE_BLOCK_EDITOR?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
