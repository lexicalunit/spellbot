# ECS Task Definition - prod
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
      portMappings = [
        {
          containerPort = 8125
          protocol      = "udp"
        },
        {
          containerPort = 8126
          protocol      = "tcp"
      }]
      environment = [
        {
          name  = "DD_SITE"
          value = "datadoghq.com"
        },
        {
          name  = "ECS_FARGATE"
          value = "true"
        },
        {
          name  = "DD_ENV"
          value = "prod"
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
        },
        {
          name  = "API_BASE_URL"
          value = "https://${local.prod_domain_name}"
        }
      ]
      secrets = [
        {
          name      = "DD_API_KEY"
          valueFrom = "${aws_secretsmanager_secret.spellbot_prod.arn}:DD_API_KEY::"
        },
        {
          name      = "DD_APP_KEY"
          valueFrom = "${aws_secretsmanager_secret.spellbot_prod.arn}:DD_APP_KEY::"
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
      image     = "${data.aws_ssm_parameter.spellbot_prod_image_uri.value}"
      essential = true

      environment = [
        {
          name  = "DD_SERVICE"
          value = "spellbot"
        },
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
          value = "prod"
        },
        {
          name  = "ENVIRONMENT"
          value = "prod"
        },
        {
          name  = "REDIS_URL"
          value = "redis://${aws_elasticache_replication_group.main.primary_endpoint_address}:${aws_elasticache_replication_group.main.port}/0"
        },
        {
          name  = "API_BASE_URL"
          value = "https://${local.prod_domain_name}"
        }
      ]

      secrets = [
        {
          name      = "DD_API_KEY"
          valueFrom = "${aws_secretsmanager_secret.spellbot_prod.arn}:DD_API_KEY::"
        },
        {
          name      = "DD_APP_KEY"
          valueFrom = "${aws_secretsmanager_secret.spellbot_prod.arn}:DD_APP_KEY::"
        },
        {
          name      = "BOT_TOKEN"
          valueFrom = "${aws_secretsmanager_secret.spellbot_prod.arn}:BOT_TOKEN::"
        },
        {
          name      = "SPELLTABLE_USERS"
          valueFrom = "${aws_secretsmanager_secret.spellbot_prod.arn}:SPELLTABLE_USERS::"
        },
        {
          name      = "SPELLTABLE_PASSES"
          valueFrom = "${aws_secretsmanager_secret.spellbot_prod.arn}:SPELLTABLE_PASSES::"
        },
        {
          name      = "SPELLTABLE_AUTH_KEY"
          valueFrom = "${aws_secretsmanager_secret.spellbot_prod.arn}:SPELLTABLE_AUTH_KEY::"
        },
        {
          name      = "TABLESTREAM_AUTH_KEY"
          valueFrom = "${aws_secretsmanager_secret.spellbot_prod.arn}:TABLESTREAM_AUTH_KEY::"
        },
        {
          name      = "SPELLTABLE_CLIENT_ID"
          valueFrom = "${aws_secretsmanager_secret.spellbot_stage.arn}:SPELLTABLE_CLIENT_ID::"
        },
        {
          name      = "SPELLTABLE_API_KEY"
          valueFrom = "${aws_secretsmanager_secret.spellbot_stage.arn}:SPELLTABLE_API_KEY::"
        },
        {
          name      = "DATABASE_URL"
          valueFrom = "${data.aws_secretsmanager_secret.prod_db_password.arn}:DB_URL::"
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
      image     = "${data.aws_ssm_parameter.spellbot_prod_image_uri.value}"
      essential = true

      portMappings = [
        {
          containerPort = 80
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "DD_SERVICE"
          value = "spellapi"
        },
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
          value = "prod"
        },
        {
          name  = "ENVIRONMENT"
          value = "prod"
        },
        {
          name  = "PORT"
          value = "80"
        },
        {
          name  = "HOST"
          value = "0.0.0.0"
        },
        {
          name  = "REDIS_URL"
          value = "redis://${aws_elasticache_replication_group.main.primary_endpoint_address}:${aws_elasticache_replication_group.main.port}"
        }
      ]

      secrets = [
        {
          name      = "DD_API_KEY"
          valueFrom = "${aws_secretsmanager_secret.spellbot_prod.arn}:DD_API_KEY::"
        },
        {
          name      = "DD_APP_KEY"
          valueFrom = "${aws_secretsmanager_secret.spellbot_prod.arn}:DD_APP_KEY::"
        },
        {
          name      = "DATABASE_URL"
          valueFrom = "${data.aws_secretsmanager_secret.prod_db_password.arn}:DB_URL::"
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
    Environment = "prod"
  }
}
