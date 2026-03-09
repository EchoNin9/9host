# Cognito Auth (Task 1.9)

Cognito User Pool `9host-user-pool` provides auth for the frontend.

## Outputs (from `tofu output`)

| Output | Description |
|--------|-------------|
| `cognito_user_pool_id` | User Pool ID (e.g. `us-east-1_xxx`) |
| `cognito_client_id` | App client ID for SPA |
| `cognito_domain` | Hosted UI domain (e.g. `9host-auth.auth.us-east-1.amazoncognito.com`) |
| `cognito_issuer_url` | OIDC issuer URL |

## Frontend config

Use these values for Amplify, `amazon-cognito-identity-js`, or any OIDC client:

```ts
const cognitoConfig = {
  userPoolId: '<cognito_user_pool_id>',
  clientId: '<cognito_client_id>',
  domain: '9host-auth.auth.us-east-1.amazoncognito.com',
  redirectSignIn: 'https://stage.echo9.net', // or prod, or http://localhost:5173
  redirectSignOut: 'https://stage.echo9.net',
  scopes: ['openid', 'email', 'profile'],
};
```

## App client

- **Name:** 9host-frontend
- **Type:** Public (no secret) — SPA with PKCE
- **Grant:** Authorization code
- **Callback URLs:** stage.echo9.net, prod.echo9.net, localhost:5173, localhost:5173/auth/callback

## Groups

| Group | Precedence | Description |
|-------|------------|-------------|
| admin | 1 | Tenant admin |
| manager | 2 | Tenant manager |
| editor | 3 | Tenant editor |
| member | 4 | Tenant member |

User roles are stored in DynamoDB (`TENANT#{slug}#USER#{sub}#PROFILE`). Cognito groups can be used for cross-tenant admin or platform-level permissions.
