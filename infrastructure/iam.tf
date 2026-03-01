# ============================================
# ECS Execution Role (for pulling images, logging)
# ============================================

resource "aws_iam_role" "ecs_execution" {
  name = "${var.project_name}-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-ecs-execution-role"
  }
}

resource "aws_iam_role_policy" "ecs_execution" {
  name = "${var.project_name}-ecs-execution-policy"
  role = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.mcp_server.arn}:*"
      }
    ]
  })
}

# ============================================
# MCP Server Task Role (for CloudWatch Logs access)
# ============================================

resource "aws_iam_role" "mcp_server_task" {
  name = "${var.project_name}-mcp-server-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-mcp-server-task-role"
  }
}

resource "aws_iam_role_policy" "mcp_server_cloudwatch" {
  name = "${var.project_name}-mcp-cloudwatch-policy"
  role = aws_iam_role.mcp_server_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "logs:GetLogEvents",
          "logs:FilterLogEvents",
          "logs:StartQuery",
          "logs:StopQuery",
          "logs:GetQueryResults",
          "logs:GetLogRecord"
        ]
        Resource = "*"
      }
    ]
  })
}

# ============================================
# Lambda Execution Role
# ============================================

resource "aws_iam_role" "lambda" {
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-lambda-role"
  }
}

# Lambda VPC Access
resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# Lambda CloudWatch Logs
resource "aws_iam_role_policy" "lambda_logs" {
  name = "${var.project_name}-lambda-logs-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "logs:FilterLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:*:*"
      }
    ]
  })
}

# Lambda Bedrock Access
resource "aws_iam_role_policy" "lambda_bedrock" {
  name = "${var.project_name}-lambda-bedrock-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_model_id}"
      }
    ]
  })
}

# Lambda DynamoDB Access
resource "aws_iam_role_policy" "lambda_dynamodb" {
  name = "${var.project_name}-lambda-dynamodb-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.incidents.arn,
          "${aws_dynamodb_table.incidents.arn}/index/*",
          aws_dynamodb_table.playbooks.arn,
          "${aws_dynamodb_table.playbooks.arn}/index/*",
          aws_dynamodb_table.memory.arn,
          "${aws_dynamodb_table.memory.arn}/index/*",
          aws_dynamodb_table.remediation_state.arn,
          "${aws_dynamodb_table.remediation_state.arn}/index/*",
          aws_dynamodb_table.chat_sessions.arn,
          "${aws_dynamodb_table.chat_sessions.arn}/index/*"
        ]
      }
    ]
  })
}

# Lambda CloudWatch Logs Insights (for fallback)
resource "aws_iam_role_policy" "lambda_logs_insights" {
  name = "${var.project_name}-lambda-logs-insights-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:StartQuery",
          "logs:GetQueryResults"
        ]
        Resource = "*"
      }
    ]
  })
}

# Lambda CloudWatch Alarms Access (for creating/managing alarms)
resource "aws_iam_role_policy" "lambda_cloudwatch_alarms" {
  name = "${var.project_name}-lambda-cloudwatch-alarms-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricAlarm",
          "cloudwatch:DescribeAlarms",
          "cloudwatch:DeleteAlarms",
          "cloudwatch:SetAlarmState"
        ]
        Resource = "*"
      }
    ]
  })
}

# Lambda KB S3 Access (for uploading and reading KB documents)
resource "aws_iam_role_policy" "lambda_kb_s3" {
  name = "${var.project_name}-lambda-kb-s3-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject"
        ]
        Resource = "${aws_s3_bucket.kb_documents.arn}/*"
      }
    ]
  })
}

# Lambda KB DynamoDB Access (for kb_documents and kb_chunks tables)
resource "aws_iam_role_policy" "lambda_kb_dynamodb" {
  name = "${var.project_name}-lambda-kb-dynamodb-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Scan",
          "dynamodb:BatchWriteItem"
        ]
        Resource = [
          aws_dynamodb_table.kb_documents.arn,
          "${aws_dynamodb_table.kb_documents.arn}/index/*",
          aws_dynamodb_table.kb_chunks.arn,
          "${aws_dynamodb_table.kb_chunks.arn}/index/*"
        ]
      }
    ]
  })
}

# Lambda Titan Embed Access (for generating KB embeddings)
resource "aws_iam_role_policy" "lambda_titan_embed" {
  name = "${var.project_name}-lambda-titan-embed-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["bedrock:InvokeModel"]
        Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-embed-text-v2:0"
      }
    ]
  })
}

# Lambda SSM Parameter Store Access (for GitHub token and webhook secret)
resource "aws_iam_role_policy" "lambda_ssm" {
  name = "${var.project_name}-lambda-ssm-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = [
          aws_ssm_parameter.github_token.arn,
          aws_ssm_parameter.webhook_secret.arn
        ]
      }
    ]
  })
}
