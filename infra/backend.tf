# Remote state backend. Run bootstrap first, then:
#   AWS_PROFILE=echo9 ./scripts/init-backend.sh
# Or for CI: workflows pass -backend-config via init step.
terraform {
  backend "s3" {
    key = "9host/terraform.tfstate"
  }
}
