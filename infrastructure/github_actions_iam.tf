# ============================================
# GitHub Actions IAM Role for Bedrock Access
# ============================================
# This role allows GitHub Actions to invoke Bedrock models
# using OIDC authentication (no access keys needed)

# OIDC Provider for GitHub Actions
# Note: This assumes the OIDC provider already exists in your AWS account
# If it doesn't exist, you'll need to create it manually first (see instructions below)

data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

# IAM Role for GitHub Actions
resource "aws_iam_role" "github_actions_bedrock" {
  name = "${var.project_name}-github-actions-bedrock-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = data.aws_iam_openid_connect_provider.github.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:${var.github_org}/*"
          }
        }
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-github-actions-bedrock-role"
    Description = "IAM role for GitHub Actions to access Bedrock"
  }
}

# Policy for Bedrock access
resource "aws_iam_role_policy" "github_actions_bedrock" {
  name = "${var.project_name}-github-actions-bedrock-policy"
  role = aws_iam_role.github_actions_bedrock.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/anthropic.claude-*"
      }
    ]
  })
}

# Output the role ARN (use this as AWS_ROLE_ARN secret in GitHub)
output "github_actions_bedrock_role_arn" {
  value       = aws_iam_role.github_actions_bedrock.arn
  description = "ARN of the IAM role for GitHub Actions Bedrock access. Use this as AWS_ROLE_ARN secret in GitHub repositories."
}
