# ============================================
# VPC Outputs
# ============================================

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = aws_subnet.private[*].id
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = aws_subnet.public[*].id
}

# ============================================
# DynamoDB Outputs
# ============================================

output "incidents_table_name" {
  description = "Incidents DynamoDB table name"
  value       = aws_dynamodb_table.incidents.name
}

output "incidents_table_arn" {
  description = "Incidents DynamoDB table ARN"
  value       = aws_dynamodb_table.incidents.arn
}

output "playbooks_table_name" {
  description = "Playbooks DynamoDB table name"
  value       = aws_dynamodb_table.playbooks.name
}

output "memory_table_name" {
  description = "Memory DynamoDB table name"
  value       = aws_dynamodb_table.memory.name
}

# ============================================
# MCP Server Outputs
# ============================================

output "ecr_repository_url" {
  description = "ECR repository URL for MCP server"
  value       = aws_ecr_repository.mcp_server.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.mcp.name
}

output "ecs_service_name" {
  description = "ECS service name"
  value       = aws_ecs_service.mcp_server.name
}

output "mcp_endpoint" {
  description = "MCP server internal endpoint"
  value       = "http://mcp-server.${aws_service_discovery_private_dns_namespace.mcp.name}:8000"
}

output "mcp_server_log_group" {
  description = "CloudWatch Log Group for MCP server"
  value       = aws_cloudwatch_log_group.mcp_server.name
}

# Incident MCP Server Outputs
output "incident_mcp_ecr_repository_url" {
  description = "ECR repository URL for Incident MCP server"
  value       = aws_ecr_repository.incident_mcp_server.repository_url
}

output "incident_mcp_endpoint" {
  description = "Incident MCP server internal endpoint"
  value       = "http://incident-mcp-server.${aws_service_discovery_private_dns_namespace.mcp.name}:8010"
}

output "incident_mcp_ecs_service_name" {
  description = "ECS service name for Incident MCP server"
  value       = aws_ecs_service.incident_mcp_server.name
}

# ============================================
# Lambda Outputs
# ============================================

output "lambda_function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.incident_handler.function_name
}

output "lambda_function_arn" {
  description = "Lambda function ARN"
  value       = aws_lambda_function.incident_handler.arn
}

output "lambda_function_url" {
  description = "Lambda function URL for testing"
  value       = aws_lambda_function_url.incident_handler.function_url
}

output "lambda_log_group" {
  description = "CloudWatch Log Group for Lambda"
  value       = aws_cloudwatch_log_group.lambda.name
}

# ============================================
# EventBridge Outputs
# ============================================

output "eventbridge_rule_name" {
  description = "EventBridge rule name"
  value       = aws_cloudwatch_event_rule.alarm_state_change.name
}

output "eventbridge_rule_arn" {
  description = "EventBridge rule ARN"
  value       = aws_cloudwatch_event_rule.alarm_state_change.arn
}

# ============================================
# UI (CloudFront/S3) Outputs
# ============================================

output "ui_cloudfront_url" {
  description = "CloudFront URL for UI"
  value       = "https://${aws_cloudfront_distribution.ui.domain_name}"
}

output "ui_cloudfront_distribution_id" {
  description = "CloudFront Distribution ID for UI"
  value       = aws_cloudfront_distribution.ui.id
}

output "ui_s3_bucket_name" {
  description = "S3 Bucket name for UI"
  value       = aws_s3_bucket.ui.bucket
}

# ============================================
# General Outputs
# ============================================

output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}

output "project_name" {
  description = "Project name"
  value       = var.project_name
}

output "aws_account_id" {
  description = "AWS account ID"
  value       = data.aws_caller_identity.current.account_id
}
