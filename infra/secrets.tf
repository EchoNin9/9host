# ------------------------------------------------------------------------------
# CloudNS credentials — stored in Secrets Manager (never in tfvars)
# User sets value via: aws secretsmanager put-secret-value --secret-id 9host-cloudns \
#   --secret-string '{"auth_id":12345,"password":"your-password"}'
# ------------------------------------------------------------------------------

resource "aws_secretsmanager_secret" "cloudns" {
  name        = "9host-cloudns"
  description = "ClouDNS API credentials for 9host DNS (auth_id, password)"

  tags = {
    Name = "9host-cloudns"
  }
}

resource "aws_secretsmanager_secret_version" "cloudns" {
  secret_id     = aws_secretsmanager_secret.cloudns.id
  secret_string = jsonencode({ auth_id = 0, password = "REPLACE_ME" })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# ------------------------------------------------------------------------------
# Stripe credentials (Task 3.1) — secret_key, webhook_secret, price IDs
# User sets via: aws secretsmanager put-secret-value --secret-id 9host-stripe \
#   --secret-string '{"secret_key":"sk_...","webhook_secret":"whsec_...","price_pro":"price_...","price_business":"price_..."}'
# ------------------------------------------------------------------------------

resource "aws_secretsmanager_secret" "stripe" {
  name        = "9host-stripe"
  description = "Stripe API credentials for 9host tier subscriptions"

  tags = {
    Name = "9host-stripe"
  }
}

resource "aws_secretsmanager_secret_version" "stripe" {
  secret_id     = aws_secretsmanager_secret.stripe.id
  secret_string = jsonencode({
    secret_key     = "REPLACE_ME"
    webhook_secret = "REPLACE_ME"
    price_pro      = "REPLACE_ME"
    price_business = "REPLACE_ME"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# ------------------------------------------------------------------------------
# JWT signing key for site login (Task 1.44) — non-Cognito tenant user auth
# User sets via: aws secretsmanager put-secret-value --secret-id 9host-jwt-signing-key \
#   --secret-string "$(openssl rand -base64 32)"
# ------------------------------------------------------------------------------

resource "aws_secretsmanager_secret" "jwt_signing" {
  name        = "9host-jwt-signing-key"
  description = "JWT signing key for site login (non-Cognito tenant users)"

  tags = {
    Name = "9host-jwt-signing-key"
  }
}

resource "aws_secretsmanager_secret_version" "jwt_signing" {
  secret_id     = aws_secretsmanager_secret.jwt_signing.id
  secret_string = "REPLACE_ME"

  lifecycle {
    ignore_changes = [secret_string]
  }
}
