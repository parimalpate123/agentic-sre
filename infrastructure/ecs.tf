# ECS Cluster for MCP Server
resource "aws_ecs_cluster" "mcp" {
  name = "${var.project_name}-mcp-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "${var.project_name}-mcp-cluster"
  }
}

# CloudWatch Log Group for MCP Server
resource "aws_cloudwatch_log_group" "mcp_server" {
  name              = "/ecs/${var.project_name}-mcp-server"
  retention_in_days = var.log_retention_days

  tags = {
    Name = "${var.project_name}-mcp-server-logs"
  }
}

# ECS Task Definition for MCP Server
resource "aws_ecs_task_definition" "mcp_server" {
  family                   = "${var.project_name}-mcp-server"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.mcp_cpu
  memory                   = var.mcp_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.mcp_server_task.arn

  container_definitions = jsonencode([
    {
      name      = "mcp-server"
      image     = "${aws_ecr_repository.mcp_server.repository_url}:latest"
      essential = true

      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "AWS_REGION"
          value = var.aws_region
        },
        {
          name  = "AWS_DEFAULT_REGION"
          value = var.aws_region
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.mcp_server.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "mcp"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "python -c 'import sys; sys.exit(0)' || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = {
    Name = "${var.project_name}-mcp-server-task"
  }
}

# Service Discovery for MCP Server
resource "aws_service_discovery_private_dns_namespace" "mcp" {
  name        = "${var.project_name}.local"
  description = "Private DNS namespace for MCP server"
  vpc         = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-namespace"
  }
}

resource "aws_service_discovery_service" "mcp_server" {
  name = "mcp-server"

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
    Name = "${var.project_name}-mcp-server-discovery"
  }
}

# ECS Service for MCP Server
resource "aws_ecs_service" "mcp_server" {
  name            = "${var.project_name}-mcp-server"
  cluster         = aws_ecs_cluster.mcp.id
  task_definition = aws_ecs_task_definition.mcp_server.arn
  desired_count   = var.mcp_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.mcp_server.id]
    assign_public_ip = false
  }

  service_registries {
    registry_arn = aws_service_discovery_service.mcp_server.arn
  }

  enable_execute_command = true

  tags = {
    Name = "${var.project_name}-mcp-server-service"
  }

  depends_on = [
    aws_iam_role_policy.ecs_execution,
    aws_iam_role_policy.mcp_server_cloudwatch
  ]
}
