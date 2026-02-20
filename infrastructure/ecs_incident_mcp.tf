# ============================================
# Incident MCP Server (mock ServiceNow, Jira, KB stub)
# Same pattern as Log MCP: ECR, ECS Fargate, Service Discovery
# Only created when var.enable_incident_mcp is true.
# ============================================

# ECR Repository for Incident MCP Server
resource "aws_ecr_repository" "incident_mcp_server" {
  count                = var.enable_incident_mcp ? 1 : 0
  name                 = "${var.project_name}-incident-mcp-server"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = "${var.project_name}-incident-mcp-server"
  }
}

resource "aws_ecr_lifecycle_policy" "incident_mcp_server" {
  count      = var.enable_incident_mcp ? 1 : 0
  repository = aws_ecr_repository.incident_mcp_server[0].name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 5 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 5
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# CloudWatch Log Group for Incident MCP Server
resource "aws_cloudwatch_log_group" "incident_mcp_server" {
  count             = var.enable_incident_mcp ? 1 : 0
  name              = "/ecs/${var.project_name}-incident-mcp-server"
  retention_in_days = var.log_retention_days

  tags = {
    Name = "${var.project_name}-incident-mcp-server-logs"
  }
}

# ECS Execution Role: allow logging to Incident MCP log group
resource "aws_iam_role_policy" "ecs_execution_incident_mcp_logs" {
  count  = var.enable_incident_mcp ? 1 : 0
  name   = "${var.project_name}-ecs-execution-incident-mcp-logs"
  role   = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.incident_mcp_server[0].arn}:*"
      }
    ]
  })
}

# Security Group for Incident MCP Server (port 8010 from Lambda)
resource "aws_security_group" "incident_mcp_server" {
  count       = var.enable_incident_mcp ? 1 : 0
  name        = "${var.project_name}-incident-mcp-server-sg"
  description = "Security group for Incident MCP server"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Allow HTTP from Lambda"
    from_port       = 8010
    to_port         = 8010
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda.id]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-incident-mcp-server-sg"
  }
}

# ECS Task Definition for Incident MCP Server
resource "aws_ecs_task_definition" "incident_mcp_server" {
  count                    = var.enable_incident_mcp ? 1 : 0
  family                   = "${var.project_name}-incident-mcp-server"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.mcp_cpu
  memory                   = var.mcp_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.mcp_server_task.arn

  container_definitions = jsonencode([
    {
      name      = "incident-mcp-server"
      image     = "${aws_ecr_repository.incident_mcp_server[0].repository_url}:latest"
      essential = true

      portMappings = [
        {
          containerPort = 8010
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "AWS_REGION"
          value = var.aws_region
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.incident_mcp_server[0].name
          "awslogs-region"         = var.aws_region
          "awslogs-stream-prefix"  = "incident-mcp"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8010/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = {
    Name = "${var.project_name}-incident-mcp-server-task"
  }
}

# Service Discovery for Incident MCP Server (same namespace as Log MCP)
resource "aws_service_discovery_service" "incident_mcp_server" {
  count = var.enable_incident_mcp ? 1 : 0
  name  = "incident-mcp-server"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.mcp.id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {
    failure_threshold = 1
  }

  tags = {
    Name = "${var.project_name}-incident-mcp-server-discovery"
  }
}

# ECS Service for Incident MCP Server
resource "aws_ecs_service" "incident_mcp_server" {
  count           = var.enable_incident_mcp ? 1 : 0
  name            = "${var.project_name}-incident-mcp-server"
  cluster         = aws_ecs_cluster.mcp.id
  task_definition = aws_ecs_task_definition.incident_mcp_server[0].arn
  desired_count   = var.mcp_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.incident_mcp_server[0].id]
    assign_public_ip = false
  }

  service_registries {
    registry_arn = aws_service_discovery_service.incident_mcp_server[0].arn
  }

  enable_execute_command = true

  tags = {
    Name = "${var.project_name}-incident-mcp-server-service"
  }

  depends_on = [
    aws_iam_role_policy.ecs_execution,
    aws_iam_role_policy.ecs_execution_incident_mcp_logs
  ]
}
