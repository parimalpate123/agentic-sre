# ============================================
# Elasticsearch MCP Server (cr7258/elasticsearch-mcp-server)
# Streamable HTTP transport, JSON-RPC 2.0 protocol.
# Same pattern as Incident MCP: ECR, ECS Fargate, Service Discovery.
# Only created when var.enable_elasticsearch_mcp is true.
# ============================================

# ECR Repository for ES MCP Server
resource "aws_ecr_repository" "es_mcp_server" {
  count                = var.enable_elasticsearch_mcp ? 1 : 0
  name                 = "${var.project_name}-es-mcp-server"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = "${var.project_name}-es-mcp-server"
  }
}

resource "aws_ecr_lifecycle_policy" "es_mcp_server" {
  count      = var.enable_elasticsearch_mcp ? 1 : 0
  repository = aws_ecr_repository.es_mcp_server[0].name

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

# CloudWatch Log Group for ES MCP Server
resource "aws_cloudwatch_log_group" "es_mcp_server" {
  count             = var.enable_elasticsearch_mcp ? 1 : 0
  name              = "/ecs/${var.project_name}-es-mcp-server"
  retention_in_days = var.log_retention_days

  tags = {
    Name = "${var.project_name}-es-mcp-server-logs"
  }
}

# ECS Execution Role: allow logging to ES MCP log group
resource "aws_iam_role_policy" "ecs_execution_es_mcp_logs" {
  count = var.enable_elasticsearch_mcp ? 1 : 0
  name  = "${var.project_name}-ecs-execution-es-mcp-logs"
  role  = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.es_mcp_server[0].arn}:*"
      }
    ]
  })
}

# Security Group for ES MCP Server (port 8020 from Lambda)
resource "aws_security_group" "es_mcp_server" {
  count       = var.enable_elasticsearch_mcp ? 1 : 0
  name        = "${var.project_name}-es-mcp-server-sg"
  description = "Security group for ES MCP server"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Allow HTTP from Lambda"
    from_port       = 8020
    to_port         = 8020
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
    Name = "${var.project_name}-es-mcp-server-sg"
  }
}

# ECS Task Definition for ES MCP Server
resource "aws_ecs_task_definition" "es_mcp_server" {
  count                    = var.enable_elasticsearch_mcp ? 1 : 0
  family                   = "${var.project_name}-es-mcp-server"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.es_mcp_cpu
  memory                   = var.es_mcp_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.mcp_server_task.arn

  container_definitions = jsonencode([
    {
      name      = "es-mcp-server"
      image     = "${aws_ecr_repository.es_mcp_server[0].repository_url}:latest"
      essential = true

      portMappings = [
        {
          containerPort = 8020
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "ELASTICSEARCH_HOSTS"
          value = "http://elasticsearch.${aws_service_discovery_private_dns_namespace.mcp.name}:9200"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.es_mcp_server[0].name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "es-mcp"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -sf http://localhost:8020/mcp || exit 1"]
        interval    = 30
        timeout     = 10
        retries     = 3
        startPeriod = 90
      }
    }
  ])

  tags = {
    Name = "${var.project_name}-es-mcp-server-task"
  }
}

# Service Discovery for ES MCP Server
resource "aws_service_discovery_service" "es_mcp_server" {
  count = var.enable_elasticsearch_mcp ? 1 : 0
  name  = "es-mcp-server"

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
    Name = "${var.project_name}-es-mcp-server-discovery"
  }
}

# ECS Service for ES MCP Server
resource "aws_ecs_service" "es_mcp_server" {
  count           = var.enable_elasticsearch_mcp ? 1 : 0
  name            = "${var.project_name}-es-mcp-server"
  cluster         = aws_ecs_cluster.mcp.id
  task_definition = aws_ecs_task_definition.es_mcp_server[0].arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.es_mcp_server[0].id]
    assign_public_ip = false
  }

  service_registries {
    registry_arn = aws_service_discovery_service.es_mcp_server[0].arn
  }

  enable_execute_command = true

  tags = {
    Name = "${var.project_name}-es-mcp-server-service"
  }

  depends_on = [
    aws_iam_role_policy.ecs_execution,
    aws_iam_role_policy.ecs_execution_es_mcp_logs,
    aws_ecs_service.elasticsearch
  ]
}
