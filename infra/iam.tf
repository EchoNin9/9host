data "aws_caller_identity" "current" {}

# ------------------------------------------------------------------------------
# GitHub OIDC provider (for Actions to assume IAM roles without long-lived keys)
# One per AWS account. If you already have one (e.g. from another project), import it:
#   tofu import aws_iam_openid_connect_provider.github arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com
# ------------------------------------------------------------------------------
data "tls_certificate" "github" {
  url = "https://token.actions.githubusercontent.com"
}

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.github.certificates[0].sha1_fingerprint]
}

# ------------------------------------------------------------------------------
# IAM role: GitHub Actions – Staging (develop branch)
# ------------------------------------------------------------------------------
data "aws_iam_policy_document" "github_staging_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_org_repo}:ref:refs/heads/develop"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "github_staging" {
  name               = "9host-github-actions-staging"
  assume_role_policy = data.aws_iam_policy_document.github_staging_assume.json
}

# ------------------------------------------------------------------------------
# IAM role: GitHub Actions – Production (main branch)
# ------------------------------------------------------------------------------
data "aws_iam_policy_document" "github_production_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_org_repo}:ref:refs/heads/main"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "github_production" {
  name               = "9host-github-actions-production"
  assume_role_policy = data.aws_iam_policy_document.github_production_assume.json
}

# ------------------------------------------------------------------------------
# Policy: Phase 1 deploy (ACM, Route 53). Expand as you add S3, Lambda, etc.
# ------------------------------------------------------------------------------
data "aws_iam_policy_document" "deploy" {
  statement {
    sid    = "ACM"
    effect = "Allow"
    actions = ["acm:*"]
    resources = ["*"]
  }

  # Route 53 omitted — DNS hosted on CloudNS

  statement {
    sid       = "STS"
    effect    = "Allow"
    actions   = ["sts:GetCallerIdentity"]
    resources = ["*"]
  }

  # Allow deploy role to update the deploy policy (self-update for IAM permission changes)
  statement {
    sid    = "IAMDeployPolicy"
    effect = "Allow"
    actions = [
      "iam:GetPolicy",
      "iam:GetPolicyVersion",
      "iam:ListPolicyVersions",
      "iam:CreatePolicyVersion",
      "iam:DeletePolicyVersion"
    ]
    resources = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/9host-deploy"]
  }

  statement {
    sid       = "DynamoDB"
    effect    = "Allow"
    actions   = ["dynamodb:*"]
    resources = ["arn:aws:dynamodb:*:*:table/9host-*"]
  }

  statement {
    sid    = "IAMRead"
    effect = "Allow"
    actions = [
      "iam:GetOpenIDConnectProvider",
      "iam:GetPolicy",
      "iam:GetPolicyVersion",
      "iam:GetRole",
      "iam:GetRolePolicy",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies"
    ]
    resources = [
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/token.actions.githubusercontent.com",
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/9host-*",
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/9host-*"
    ]
  }

  statement {
    sid    = "S3State"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket"
    ]
    resources = [
      "arn:aws:s3:::9host-tofu-state-*",
      "arn:aws:s3:::9host-tofu-state-*/*"
    ]
  }

  statement {
    sid    = "DynamoDBStateLock"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:DeleteItem",
      "dynamodb:ConditionCheckItem",
      "dynamodb:BatchGetItem"
    ]
    resources = ["arn:aws:dynamodb:*:*:table/9host-tofu-state-lock"]
  }

  statement {
    sid    = "S3Frontend"
    effect = "Allow"
    actions = [
      "s3:CreateBucket",
      "s3:GetBucketAcl",
      "s3:GetAccelerateConfiguration",
      "s3:GetBucketOwnershipControls",
      "s3:GetBucketPolicy",
      "s3:GetBucketPublicAccessBlock",
      "s3:GetBucketVersioning",
      "s3:GetBucketCors",
      "s3:GetBucketWebsite",
      "s3:GetBucketRequestPayment",
      "s3:GetBucketTagging",
      "s3:GetBucketLocation",
      "s3:GetBucketLogging",
      "s3:GetLifecycleConfiguration",
      "s3:GetReplicationConfiguration",
      "s3:GetBucketObjectLockConfiguration",
      "s3:GetEncryptionConfiguration",
      "s3:PutBucketOwnershipControls",
      "s3:PutBucketPolicy",
      "s3:PutBucketPublicAccessBlock",
      "s3:PutBucketVersioning",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
      "s3:GetObject"
    ]
    resources = [
      "arn:aws:s3:::9host-frontend-staging",
      "arn:aws:s3:::9host-frontend-staging/*",
      "arn:aws:s3:::9host-frontend-production",
      "arn:aws:s3:::9host-frontend-production/*"
    ]
  }

  statement {
    sid    = "Cognito"
    effect = "Allow"
    actions = [
      "cognito-idp:CreateUserPool",
      "cognito-idp:UpdateUserPool",
      "cognito-idp:DeleteUserPool",
      "cognito-idp:DescribeUserPool",
      "cognito-idp:GetUserPoolMfaConfig",
      "cognito-idp:SetUserPoolMfaConfig",
      "cognito-idp:CreateUserPoolClient",
      "cognito-idp:UpdateUserPoolClient",
      "cognito-idp:DeleteUserPoolClient",
      "cognito-idp:DescribeUserPoolClient",
      "cognito-idp:CreateUserPoolDomain",
      "cognito-idp:UpdateUserPoolDomain",
      "cognito-idp:DeleteUserPoolDomain",
      "cognito-idp:DescribeUserPoolDomain",
      "cognito-idp:CreateGroup",
      "cognito-idp:UpdateGroup",
      "cognito-idp:DeleteGroup",
      "cognito-idp:GetGroup",
      "cognito-idp:ListGroups",
      "cognito-idp:TagResource",
      "cognito-idp:UntagResource",
      "cognito-idp:ListTagsForResource"
    ]
    resources = ["*"]
  }

  statement {
    sid    = "LambdaLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:DescribeLogGroups",
      "logs:DeleteLogGroup"
    ]
    resources = ["arn:aws:logs:*:*:log-group:/aws/lambda/9host-*"]
  }

  # Lambda: deploy + read for OpenTofu state refresh (GetFunction, GetPolicy, etc.)
  statement {
    sid    = "Lambda"
    effect = "Allow"
    actions = [
      "lambda:CreateFunction",
      "lambda:DeleteFunction",
      "lambda:GetFunction",
      "lambda:GetFunctionCodeSigningConfig",
      "lambda:GetFunctionConfiguration",
      "lambda:GetPolicy",
      "lambda:ListVersionsByFunction",
      "lambda:UpdateFunctionCode",
      "lambda:UpdateFunctionConfiguration",
      "lambda:AddPermission",
      "lambda:RemovePermission",
      "lambda:TagResource",
      "lambda:UntagResource",
      "lambda:ListTags"
    ]
    resources = ["arn:aws:lambda:*:*:function:9host-*"]
  }

  statement {
    sid    = "APIGateway"
    effect = "Allow"
    actions = [
      "apigateway:GET",
      "apigateway:POST",
      "apigateway:PUT",
      "apigateway:PATCH",
      "apigateway:DELETE"
    ]
    resources = ["arn:aws:apigateway:*::/apis/*", "arn:aws:apigateway:*::/apis/*/*"]
  }

  statement {
    sid    = "CloudFront"
    effect = "Allow"
    actions = [
      "cloudfront:CreateDistribution",
      "cloudfront:UpdateDistribution",
      "cloudfront:GetDistribution",
      "cloudfront:GetDistributionConfig",
      "cloudfront:DeleteDistribution",
      "cloudfront:TagResource",
      "cloudfront:ListTagsForResource",
      "cloudfront:ListDistributions",
      "cloudfront:CreateOriginAccessControl",
      "cloudfront:GetOriginAccessControl",
      "cloudfront:UpdateOriginAccessControl",
      "cloudfront:DeleteOriginAccessControl",
      "cloudfront:ListOriginAccessControls",
      "cloudfront:CreateInvalidation"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "deploy" {
  name   = "9host-deploy"
  policy = data.aws_iam_policy_document.deploy.json
}

resource "aws_iam_role_policy_attachment" "github_staging_deploy" {
  role       = aws_iam_role.github_staging.name
  policy_arn = aws_iam_policy.deploy.arn
}

resource "aws_iam_role_policy_attachment" "github_production_deploy" {
  role       = aws_iam_role.github_production.name
  policy_arn = aws_iam_policy.deploy.arn
}
