# ECS Task Definition for the environment

locals {
  domain_name = "${var.env_name}.${var.root_domain}"

  # Common environment variables shared across all containers
  common_env = {
    DD_SITE                               = "datadoghq.com"
    ECS_FARGATE                           = "true"
    DD_DOGSTATSD_NON_LOCAL_TRAFFIC        = "true"
    DD_APM_ENABLED                        = "true"
    DD_APM_NON_LOCAL_TRAFFIC              = "true"
    DD_LOG_FORMAT                         = "json"
    DD_TRACE_AGENT_HOSTNAME               = "localhost"
    DD_TRACE_AGENT_PORT                   = "8126"
    DD_TRACE_WRAP_SPAN_NAME_INCLUDE_CLASS = "true"
  }

  # Common app environment variables
  app_common_env = {
    DD_SERVICE                    = "spellbot"
    OWNER_XID                     = "82174992933986304"
    PATREON_CAMPAIGN              = "5809116"
    GIRUDO_DEFAULT_FORMAT_UUID    = "15d43935-9374-416f-8ddd-ef71ed50670e"
    GIRUDO_DEFAULT_TCG_UUID       = "ca8b23af-c9dd-4b16-bfaf-ee351caf4a16"
    GIRUDO_DEFAULT_TCG_MAGIC_UUID = "ca8b23af-c9dd-4b16-bfaf-ee351caf4a16"
  }

  # Secret names for the main spellbot container
  app_secret_names = [
    "DD_API_KEY",
    "DD_APP_KEY",
    "BOT_TOKEN",
    "SECRET_TOKEN",
    "TABLESTREAM_AUTH_KEY",
    "CONVOKE_API_KEY",
    "PLAYGROUP_LIVE_API_KEY",
    "EDHLAB_API_KEY",
    "PATREON_TOKEN",
    "GIRUDO_EMAILS",
    "GIRUDO_PASSWORDS"
  ]

  # Secret names for the gunicorn container
  api_secret_names = [
    "DD_API_KEY",
    "DD_APP_KEY",
    "BOT_TOKEN",
    "SECRET_TOKEN"
  ]
}

resource "aws_ecs_task_definition" "spellbot" {
  family                   = "spellbot-${var.env_name}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024" # 1 vCPU
  memory                   = "3072" # 3 GB
  execution_role_arn       = var.ecs_task_execution_role_arn
  task_role_arn            = var.ecs_task_role_arn

  runtime_platform {
    cpu_architecture = "ARM64"
  }

  container_definitions = jsonencode([
    # Datadog Agent container
    {
      name      = "datadog-agent"
      image     = "gcr.io/datadoghq/agent:7"
      essential = false
      portMappings = [
        { containerPort = 8125, protocol = "udp" },
        { containerPort = 8126, protocol = "tcp" }
      ]
      environment = [
        for k, v in merge(local.common_env, {
          DD_ENV       = var.env_name
          API_BASE_URL = "https://${local.domain_name}"
        }) : { name = k, value = v }
      ]
      secrets = [
        { name = "DD_API_KEY", valueFrom = "${aws_secretsmanager_secret.spellbot.arn}:DD_API_KEY::" },
        { name = "DD_APP_KEY", valueFrom = "${aws_secretsmanager_secret.spellbot.arn}:DD_APP_KEY::" }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.spellbot.name
          "awslogs-region"        = "us-east-1"
          "awslogs-stream-prefix" = "datadog"
        }
      }
    },

    # Main SpellBot container
    {
      name      = "spellbot"
      image     = data.aws_ssm_parameter.spellbot_image_uri.value
      essential = true
      environment = [
        for k, v in merge(local.common_env, local.app_common_env, {
          DD_ENV       = var.env_name
          ENVIRONMENT  = var.env_name
          API_BASE_URL = "https://${local.domain_name}"
          REDIS_URL    = "rediss://${var.elasticache_endpoint}:${var.elasticache_port}/${var.redis_db}"
        }) : { name = k, value = v }
      ]
      secrets = concat(
        [for name in local.app_secret_names : { name = name, valueFrom = "${aws_secretsmanager_secret.spellbot.arn}:${name}::" }],
        [{ name = "DATABASE_URL", valueFrom = "${data.aws_secretsmanager_secret.db_password.arn}:DB_URL::" }]
      )
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.spellbot.name
          "awslogs-region"        = "us-east-1"
          "awslogs-stream-prefix" = "spellbot"
        }
      }
      dependsOn = [{ containerName = "datadog-agent", condition = "START" }]
    },

    # Gunicorn API container
    {
      name         = "spellbot-gunicorn"
      command      = ["./start.sh", "spellapi"]
      image        = data.aws_ssm_parameter.spellbot_image_uri.value
      essential    = true
      portMappings = [{ containerPort = 80, protocol = "tcp" }]
      environment = [
        for k, v in merge(local.common_env, {
          DD_SERVICE  = "spellapi"
          DD_ENV      = var.env_name
          ENVIRONMENT = var.env_name
          PORT        = "80"
          HOST        = "0.0.0.0"
          REDIS_URL   = "rediss://${var.elasticache_endpoint}:${var.elasticache_port}"
        }) : { name = k, value = v }
      ]
      secrets = concat(
        [for name in local.api_secret_names : { name = name, valueFrom = "${aws_secretsmanager_secret.spellbot.arn}:${name}::" }],
        [{ name = "DATABASE_URL", valueFrom = "${data.aws_secretsmanager_secret.db_password.arn}:DB_URL::" }]
      )
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.spellbot.name
          "awslogs-region"        = "us-east-1"
          "awslogs-stream-prefix" = "gunicorn"
        }
      }
      dependsOn = [{ containerName = "datadog-agent", condition = "START" }]
    }
  ])

  tags = {
    Name        = "spellbot-${var.env_name}-task-definition"
    Environment = var.env_name
  }
}
