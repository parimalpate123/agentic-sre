# SSM Parameter Store for GitHub Token
# This stores the GitHub token securely instead of in environment variables

resource "aws_ssm_parameter" "github_token" {
  name        = "/${var.project_name}/github/token"
  description = "GitHub personal access token for auto-remediation (repo permissions required)"
  type        = "SecureString"
  value       = "CHANGE_ME" # This should be updated via AWS CLI or Console

  tags = {
    Name        = "${var.project_name}-github-token"
    Environment = var.environment
  }

  lifecycle {
    ignore_changes = [value]
    # This allows the parameter to be updated outside of Terraform
    # Use: aws ssm put-parameter --name "/sre-poc/github/token" --value "ghp_xxx" --type "SecureString" --overwrite
  }
}

# SSM Parameter for Webhook Secret Token
# This token is used to authenticate webhook requests from GitHub Actions
resource "aws_ssm_parameter" "webhook_secret" {
  name        = "/${var.project_name}/webhook/secret"
  description = "Secret token for remediation webhook authentication"
  type        = "SecureString"
  value       = "CHANGE_ME"  # Generate a secure random token and update via AWS CLI

  tags = {
    Name        = "${var.project_name}-webhook-secret"
    Environment = var.environment
  }

  lifecycle {
    ignore_changes = [value]
    # This allows the parameter to be updated outside of Terraform
    # Use: aws ssm put-parameter --name "/sre-poc/webhook/secret" --value "your-secret-token" --type "SecureString" --overwrite
  }
}
