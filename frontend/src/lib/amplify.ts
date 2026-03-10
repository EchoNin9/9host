/**
 * Amplify configuration for Cognito auth.
 * Uses VITE_COGNITO_* env vars (set in CI for stage/prod builds).
 */

import { Amplify } from "aws-amplify"

const userPoolId = import.meta.env.VITE_COGNITO_USER_POOL_ID as string | undefined
const userPoolClientId = import.meta.env.VITE_COGNITO_CLIENT_ID as string | undefined

if (userPoolId && userPoolClientId) {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId,
        userPoolClientId,
        loginWith: {
          email: true,
        },
        signUpVerificationMethod: "code",
        userAttributes: {
          email: { required: true },
        },
      },
    },
  })
}
