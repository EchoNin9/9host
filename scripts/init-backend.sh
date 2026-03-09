#!/usr/bin/env bash
# Initialize OpenTofu with S3 backend. Run from repo root.
# Requires: bootstrap applied, AWS_PROFILE=echo9 (or AWS credentials)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(cd "$SCRIPT_DIR/../infra" && pwd)"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET="9host-tofu-state-${ACCOUNT_ID}"
TABLE="9host-tofu-state-lock"
REGION="${AWS_REGION:-us-east-1}"

cat > "$INFRA_DIR/backend-config.hcl" << EOF
bucket         = "$BUCKET"
key            = "9host/terraform.tfstate"
region         = "$REGION"
dynamodb_table = "$TABLE"
EOF

echo "Backend config: bucket=$BUCKET, table=$TABLE"
cd "$INFRA_DIR"

# If migrating from local state, use -migrate-state and pipe yes
if [ -f "terraform.tfstate" ] && [ ! -f ".terraform/terraform.tfstate" ]; then
  echo "Migrating existing state to S3..."
  echo "yes" | tofu init -migrate-state -lock=false -backend-config=backend-config.hcl
else
  tofu init -reconfigure -backend-config=backend-config.hcl
fi
