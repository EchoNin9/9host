# Copy to backend-config.hcl (gitignored) or pass via -backend-config.
# Run bootstrap first: cd infra/bootstrap && tofu init && tofu apply
# Then: ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
bucket         = "9host-tofu-state-ACCOUNT_ID"
key            = "9host/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "9host-tofu-state-lock"
