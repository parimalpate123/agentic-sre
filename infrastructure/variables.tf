variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name used as prefix for all resources"
  type        = string
  default     = "sre-poc"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

# Lambda Configuration
variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 300
}

variable "lambda_memory" {
  description = "Lambda function memory in MB"
  type        = number
  default     = 1024
}

# Bedrock Configuration
variable "bedrock_model_id" {
  description = "AWS Bedrock model ID for Claude (chat operations)"
  type        = string
  default     = "anthropic.claude-3-5-sonnet-20240620-v1:0"
}

variable "bedrock_model_id_diagnosis" {
  description = "AWS Bedrock model ID for diagnosis (default: Claude 3 Haiku for higher quota - 100 req/min)"
  type        = string
  default     = "anthropic.claude-3-haiku-20240307-v1:0"
}

# MCP Server Configuration
variable "mcp_cpu" {
  description = "CPU units for MCP server (256 = 0.25 vCPU)"
  type        = number
  default     = 256
}

variable "mcp_memory" {
  description = "Memory for MCP server in MB"
  type        = number
  default     = 512
}

variable "mcp_desired_count" {
  description = "Number of MCP server tasks to run"
  type        = number
  default     = 1
}

# Logging
variable "log_retention_days" {
  description = "CloudWatch Logs retention in days"
  type        = number
  default     = 7
}

# GitHub Configuration
variable "github_org" {
  description = "GitHub organization or username for service repositories"
  type        = string
  default     = ""
}

# Incident MCP (ServiceNow, Jira) - optional, on by default
variable "enable_incident_mcp" {
  description = "Deploy Incident MCP server (ECS/ECR) for ServiceNow and Jira integration"
  type        = bool
  default     = true
}

# Note: github_token is stored in SSM Parameter Store, not as a Terraform variable
# Use AWS CLI or Console to set it: 
# aws ssm put-parameter --name "/sre-poc/github/token" --value "<YOUR_GITHUB_PAT>" --type "SecureString"
