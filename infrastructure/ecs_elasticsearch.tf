# ============================================
# Elasticsearch (single-node, APM data only)
# Fargate task on existing ECS cluster.
# Only created when var.enable_elasticsearch_mcp is true.
# ============================================

# CloudWatch Log Group for Elasticsearch
resource "aws_cloudwatch_log_group" "elasticsearch" {
  count             = var.enable_elasticsearch_mcp ? 1 : 0
  name              = "/ecs/${var.project_name}-elasticsearch"
  retention_in_days = var.log_retention_days

  tags = {
    Name = "${var.project_name}-elasticsearch-logs"
  }
}

# ECS Execution Role: allow logging to Elasticsearch log group
resource "aws_iam_role_policy" "ecs_execution_elasticsearch_logs" {
  count = var.enable_elasticsearch_mcp ? 1 : 0
  name  = "${var.project_name}-ecs-execution-elasticsearch-logs"
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
        Resource = "${aws_cloudwatch_log_group.elasticsearch[0].arn}:*"
      }
    ]
  })
}

# Security Group for Elasticsearch (port 9200 from Lambda + ES MCP)
resource "aws_security_group" "elasticsearch" {
  count       = var.enable_elasticsearch_mcp ? 1 : 0
  name        = "${var.project_name}-elasticsearch-sg"
  description = "Security group for Elasticsearch"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Allow from Lambda"
    from_port       = 9200
    to_port         = 9200
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda.id]
  }

  ingress {
    description     = "Allow from ES MCP server"
    from_port       = 9200
    to_port         = 9200
    protocol        = "tcp"
    security_groups = [aws_security_group.es_mcp_server[0].id]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-elasticsearch-sg"
  }
}

# ECS Task Definition for Elasticsearch
resource "aws_ecs_task_definition" "elasticsearch" {
  count                    = var.enable_elasticsearch_mcp ? 1 : 0
  family                   = "${var.project_name}-elasticsearch"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.es_cpu
  memory                   = var.es_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.mcp_server_task.arn

  container_definitions = jsonencode([
    {
      name      = "elasticsearch"
      image     = "docker.elastic.co/elasticsearch/elasticsearch:8.12.0"
      essential = true

      portMappings = [
        {
          containerPort = 9200
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "discovery.type"
          value = "single-node"
        },
        {
          name  = "xpack.security.enabled"
          value = "false"
        },
        {
          name  = "ES_JAVA_OPTS"
          value = "-Xms512m -Xmx512m"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.elasticsearch[0].name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "elasticsearch"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -sf http://localhost:9200/_cluster/health || exit 1"]
        interval    = 30
        timeout     = 10
        retries     = 5
        startPeriod = 120
      }
    }
  ])

  tags = {
    Name = "${var.project_name}-elasticsearch-task"
  }
}

# Service Discovery for Elasticsearch
resource "aws_service_discovery_service" "elasticsearch" {
  count = var.enable_elasticsearch_mcp ? 1 : 0
  name  = "elasticsearch"

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
    Name = "${var.project_name}-elasticsearch-discovery"
  }
}

# ECS Service for Elasticsearch
resource "aws_ecs_service" "elasticsearch" {
  count           = var.enable_elasticsearch_mcp ? 1 : 0
  name            = "${var.project_name}-elasticsearch"
  cluster         = aws_ecs_cluster.mcp.id
  task_definition = aws_ecs_task_definition.elasticsearch[0].arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.elasticsearch[0].id]
    assign_public_ip = false
  }

  service_registries {
    registry_arn = aws_service_discovery_service.elasticsearch[0].arn
  }

  enable_execute_command = true

  tags = {
    Name = "${var.project_name}-elasticsearch-service"
  }

  depends_on = [
    aws_iam_role_policy.ecs_execution,
    aws_iam_role_policy.ecs_execution_elasticsearch_logs
  ]
}
