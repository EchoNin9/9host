# ------------------------------------------------------------------------------
# Cognito User Pool (9host-user-pool) for auth — Task 1.9
# App client for frontend SPA (stage.echo9.net, prod.echo9.net).
# Groups: admin, manager, editor, member (per docs/SCHEMA.md).
# ------------------------------------------------------------------------------

resource "aws_cognito_user_pool" "main" {
  name = "9host-user-pool"

  # Email sign-in (standard attributes: email, name)
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  # Password policy
  password_policy {
    minimum_length                   = 8
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                 = true
    require_symbols                 = false
    temporary_password_validity_days = 7
  }

  # Account recovery
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  # Email verification (Cognito default)
  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
    email_subject        = "9host — Verify your email"
    email_message        = "Your verification code is {####}"
  }

  # MFA: optional (OFF by default)
  mfa_configuration = "OFF"

  # User attribute update: allow email/name updates
  user_attribute_update_settings {
    attributes_require_verification_before_update = ["email"]
  }

  tags = {
    Name = "9host-user-pool"
  }
}

# Cognito domain for hosted UI (e.g. 9host-auth.auth.us-east-1.amazoncognito.com)
resource "aws_cognito_user_pool_domain" "main" {
  domain       = "9host-auth"
  user_pool_id = aws_cognito_user_pool.main.id
}

# App client for frontend SPA — public client, PKCE
resource "aws_cognito_user_pool_client" "frontend" {
  name         = "9host-frontend"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret                      = false
  supported_identity_providers         = ["COGNITO"]
  callback_urls = concat(
    [for d in var.domains : "https://stage.${d}"],
    [for d in var.domains : "https://prod.${d}"],
    ["http://localhost:5173", "http://localhost:5173/auth/callback"]
  )
  logout_urls = concat(
    [for d in var.domains : "https://stage.${d}"],
    [for d in var.domains : "https://prod.${d}"],
    ["http://localhost:5173"]
  )
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  prevent_user_existence_errors        = "ENABLED"
  enable_token_revocation              = true
  access_token_validity                = 1   # hours
  id_token_validity                    = 1   # hours
  refresh_token_validity               = 30  # days
  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }
}

# Superadmin group — platform-level vendor/owner (Task 1.21)
resource "aws_cognito_user_group" "superadmin" {
  name         = "superadmin"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Platform admin — can list all tenants, impersonate"
  precedence   = 0
}

# Cognito groups (admin, manager, editor, member) — per docs/SCHEMA.md
resource "aws_cognito_user_group" "admin" {
  name         = "admin"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Tenant admin"
  precedence   = 1
}

resource "aws_cognito_user_group" "manager" {
  name         = "manager"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Tenant manager"
  precedence   = 2
}

resource "aws_cognito_user_group" "editor" {
  name         = "editor"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Tenant editor"
  precedence   = 3
}

resource "aws_cognito_user_group" "member" {
  name         = "member"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Tenant member"
  precedence   = 4
}
