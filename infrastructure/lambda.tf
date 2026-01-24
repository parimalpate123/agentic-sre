# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.project_name}-incident-handler"
  retention_in_days = var.log_retention_days

  tags = {
    Name = "${var.project_name}-lambda-logs"
  }
}

# Lambda Function
resource "aws_lambda_function" "incident_handler" {
  function_name = "${var.project_name}-incident-handler"
  role          = aws_iam_role.lambda.arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.11"
  timeout       = var.lambda_timeout
  memory_size   = var.lambda_memory

  # Placeholder - will be updated by deployment script
  filename         = "${path.module}/lambda_placeholder.zip"
  source_code_hash = fileexists("${path.module}/lambda_placeholder.zip") ? filebase64sha256("${path.module}/lambda_placeholder.zip") : null

  # VPC Configuration
  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      # Bedrock Configuration
      BEDROCK_MODEL_ID = var.bedrock_model_id
      BEDROCK_MODEL_ID_DIAGNOSIS = var.bedrock_model_id_diagnosis
      BEDROCK_REGION   = var.aws_region

      # DynamoDB Tables
      INCIDENTS_TABLE = aws_dynamodb_table.incidents.name
      PLAYBOOKS_TABLE = aws_dynamodb_table.playbooks.name
      MEMORY_TABLE    = aws_dynamodb_table.memory.name

      # MCP Server Endpoint
      MCP_ENDPOINT = "http://mcp-server.${aws_service_discovery_private_dns_namespace.mcp.name}:8000"

      # MCP Client Toggle (default: true - use MCP for chat queries)
      USE_MCP_CLIENT = "true"

      # Logging
      LOG_LEVEL  = "INFO"

      # GitHub Configuration (for auto-remediation code fixes)
      # Note: GITHUB_TOKEN is read from SSM Parameter Store at runtime
      GITHUB_ORG = var.github_org
      GITHUB_TOKEN_SSM_PARAM = aws_ssm_parameter.github_token.name

      # AWS_REGION is reserved and set automatically by Lambda
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda,
    aws_iam_role_policy.lambda_logs,
    aws_iam_role_policy.lambda_bedrock,
    aws_iam_role_policy.lambda_dynamodb,
    aws_iam_role_policy.lambda_ssm,
    aws_iam_role_policy_attachment.lambda_vpc,
    aws_ssm_parameter.github_token
  ]

  tags = {
    Name = "${var.project_name}-incident-handler"
  }
}

# Lambda Function URL (for manual testing)
resource "aws_lambda_function_url" "incident_handler" {
  function_name      = aws_lambda_function.incident_handler.function_name
  authorization_type = "NONE"

  cors {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST"]
    allow_headers = ["content-type"]
    max_age       = 86400
  }
}
