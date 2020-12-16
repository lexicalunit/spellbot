declare global {
  namespace NodeJS {
    interface ProcessEnv {
      REACT_APP_CLIENT_ID: string
      REACT_APP_REDIRECT_URI: string
      NODE_ENV: "development" | "production"
      PWD: string
    }
  }
}
