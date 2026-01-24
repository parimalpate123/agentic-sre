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
