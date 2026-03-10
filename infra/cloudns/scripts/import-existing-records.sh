#!/usr/bin/env bash
# List CloudNS CNAME record IDs for import. Run from repo root.
# Usage: AWS_PROFILE=echo9 AWS_REGION=us-east-1 ./infra/cloudns/scripts/import-existing-records.sh
# Requires: jq, curl, AWS CLI.
set -e

ZONE="${1:-echo9.net}"
INFRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$INFRA_DIR"

SECRET_ARN=$(tofu output -raw cloudns_secret_arn 2>/dev/null) || { echo "Run tofu apply from infra/ first"; exit 1; }
SECRET_JSON=$(aws secretsmanager get-secret-value --secret-id "$SECRET_ARN" --query SecretString --output text)
AUTH_ID=$(echo "$SECRET_JSON" | jq -r '.auth_id')
PASSWORD=$(echo "$SECRET_JSON" | jq -r '.password')

RECORDS=$(curl -s "https://api.cloudns.net/dns/records.json" \
  -d "auth-id=$AUTH_ID" \
  -d "auth-password=$PASSWORD" \
  -d "domain-name=$ZONE" \
  -d "rows-per-page=100")

echo "CNAME records in $ZONE:"
echo "$RECORDS" | jq -r '.[] | select(.type == "CNAME") | "  host=\"\(.host)\" id=\(.id)"'
echo ""
echo "Import commands (run from infra/cloudns/):"
echo "$RECORDS" | jq -r --arg z "$ZONE" '
  .[] | select(.type == "CNAME") |
  if .host == "stage" then "  tofu import cloudns_dns_record.stage \($z)/\(.id)"
  elif .host == "prod" then "  tofu import cloudns_dns_record.prod \($z)/\(.id)"
  elif (.host | test("^_[a-f0-9]+\\.")) then
    if (.host | endswith(".stage")) then "  tofu import \"cloudns_dns_record.acm_validation[\\\"stage.\($z)\\\"]\" \($z)/\(.id)"
    else "  tofu import \"cloudns_dns_record.acm_validation[\\\"prod.\($z)\\\"]\" \($z)/\(.id)"
    end
  else empty
  end
' 2>/dev/null || echo "  (get IDs from CloudNS dashboard, then: tofu import cloudns_dns_record.NAME echo9.net/ID)"
