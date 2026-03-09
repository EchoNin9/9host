# Use default credential chain (env vars in CI, AWS_PROFILE locally).
provider "aws" {
  region = var.aws_region
}

# ACM for CloudFront must be in us-east-1
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}
