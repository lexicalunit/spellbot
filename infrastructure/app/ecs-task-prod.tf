# ECS Task Definition - Production
resource "aws_ecs_task_definition" "spellbot_prod" {
  family                   = "spellbot-prod"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "2048" # 2 vCPU
  memory                   = "6144" # 6 GB
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn
  runtime_platform {
    cpu_architecture = "ARM64"
  }
  container_definitions = jsonencode([
    {
      name      = "datadog-agent"
      image     = "gcr.io/datadoghq/agent:7"
      essential = false
      memory    = 512

      environment = [
        {
          name  = "DD_API_KEY"
          value = "your-datadog-api-key" # Replace with actual key or use secrets
        },
        {
          name  = "DD_SITE"
          value = "datadoghq.com"
        },
        {
          name  = "DD_ENV"
          value = "production"
        },
        {
          name  = "DD_DOGSTATSD_NON_LOCAL_TRAFFIC"
          value = "true"
        },
        {
          name  = "DD_APM_ENABLED"
          value = "true"
        },
        {
          name  = "DD_APM_NON_LOCAL_TRAFFIC"
          value = "true"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.spellbot_prod.name
          "awslogs-region"        = "us-east-1"
          "awslogs-stream-prefix" = "datadog"
        }
      }
    },
    {
      name      = "spellbot"
      image     = "${data.aws_ssm_parameter.spellbot_production_image_uri.value}"
      essential = true
      memory    = 2048

      environment = [
        {
          name  = "DD_TRACE_AGENT_HOSTNAME"
          value = "localhost"
        },
        {
          name  = "DD_TRACE_AGENT_PORT"
          value = "8126"
        },
        {
          name  = "DD_ENV"
          value = "production"
        },
        {
          name  = "ENVIRONMENT"
          value = "production"
        },
        {
          name  = "REDIS_URL"
          value = "redis://${aws_elasticache_replication_group.main.primary_endpoint_address}:${aws_elasticache_replication_group.main.port}/0"
        }
      ]

      secrets = [
        {
          name      = "DATABASE_URL"
          valueFrom = "${data.aws_secretsmanager_secret.production_db_password.arn}:DB_URL::"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.spellbot_prod.name
          "awslogs-region"        = "us-east-1"
          "awslogs-stream-prefix" = "spellbot"
        }
      }

      dependsOn = [
        {
          containerName = "datadog-agent"
          condition     = "START"
        }
      ]
    },
    {
      name      = "spellbot-gunicorn"
      command   = ["./start.sh", "spellapi"]
      image     = "${data.aws_ssm_parameter.spellbot_production_image_uri.value}"
      essential = true
      memory    = 3584

      portMappings = [
        {
          containerPort = 80
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "DD_TRACE_AGENT_HOSTNAME"
          value = "localhost"
        },
        {
          name  = "DD_TRACE_AGENT_PORT"
          value = "8126"
        },
        {
          name  = "DD_ENV"
          value = "production"
        },
        {
          name  = "ENVIRONMENT"
          value = "production"
        },
        {
          name  = "REDIS_URL"
          value = "redis://${aws_elasticache_replication_group.main.primary_endpoint_address}:${aws_elasticache_replication_group.main.port}"
        }
      ]

      secrets = [
        {
          name      = "DATABASE_URL"
          valueFrom = "${data.aws_secretsmanager_secret.production_db_password.arn}:DB_URL::"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.spellbot_prod.name
          "awslogs-region"        = "us-east-1"
          "awslogs-stream-prefix" = "gunicorn"
        }
      }

      dependsOn = [
        {
          containerName = "datadog-agent"
          condition     = "START"
        }
      ]
    }
  ])

  tags = {
    Name        = "spellbot-prod-task-definition"
    Environment = "production"
  }
}
