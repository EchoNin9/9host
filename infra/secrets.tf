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
