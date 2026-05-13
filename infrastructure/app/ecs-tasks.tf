# ECS Task Definitions for all environments
# Uses for_each to reduce duplication between stage and prod

locals {
  environments = {
    prod = {
      domain_name    = local.prod_domain_name
      secrets_arn    = aws_secretsmanager_secret.spellbot["prod"].arn
      db_secret_arn  = data.aws_secretsmanager_secret.db_password["prod"].arn
      log_group_name = aws_cloudwatch_log_group.spellbot["prod"].name
      image_uri      = data.aws_ssm_parameter.spellbot_image_uri["prod"].value
      redis_db       = "0"
    }
    stage = {
      domain_name    = local.stage_domain_name
      secrets_arn    = aws_secretsmanager_secret.spellbot["stage"].arn
      db_secret_arn  = data.aws_secretsmanager_secret.db_password["stage"].arn
      log_group_name = aws_cloudwatch_log_group.spellbot["stage"].name
      image_uri      = data.aws_ssm_parameter.spellbot_image_uri["stage"].value
      redis_db       = "1"
    }
  }

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

  # Common secret names for the main spellbot container
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

  # Common secret names for the gunicorn container
  api_secret_names = [
    "DD_API_KEY",
    "DD_APP_KEY",
    "BOT_TOKEN",
    "SECRET_TOKEN"
  ]
}

resource "aws_ecs_task_definition" "spellbot" {
  for_each = local.environments

  family                   = "spellbot-${each.key}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024" # 1 vCPU
  memory                   = "3072" # 3 GB
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

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
          DD_ENV       = each.key
          API_BASE_URL = "https://${each.value.domain_name}"
        }) : { name = k, value = v }
      ]
      secrets = [
        { name = "DD_API_KEY", valueFrom = "${each.value.secrets_arn}:DD_API_KEY::" },
        { name = "DD_APP_KEY", valueFrom = "${each.value.secrets_arn}:DD_APP_KEY::" }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = each.value.log_group_name
          "awslogs-region"        = "us-east-1"
          "awslogs-stream-prefix" = "datadog"
        }
      }
    },

    # Main SpellBot container
    {
      name      = "spellbot"
      image     = each.value.image_uri
      essential = true
      environment = [
        for k, v in merge(local.common_env, local.app_common_env, {
          DD_ENV       = each.key
          ENVIRONMENT  = each.key
          API_BASE_URL = "https://${each.value.domain_name}"
          REDIS_URL    = "rediss://${aws_elasticache_replication_group.main.primary_endpoint_address}:${aws_elasticache_replication_group.main.port}/${each.value.redis_db}"
        }) : { name = k, value = v }
      ]
      secrets = concat(
        [for name in local.app_secret_names : { name = name, valueFrom = "${each.value.secrets_arn}:${name}::" }],
        [{ name = "DATABASE_URL", valueFrom = "${each.value.db_secret_arn}:DB_URL::" }]
      )
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = each.value.log_group_name
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
      image        = each.value.image_uri
      essential    = true
      portMappings = [{ containerPort = 80, protocol = "tcp" }]
      environment = [
        for k, v in merge(local.common_env, {
          DD_SERVICE  = "spellapi"
          DD_ENV      = each.key
          ENVIRONMENT = each.key
          PORT        = "80"
          HOST        = "0.0.0.0"
          REDIS_URL   = "rediss://${aws_elasticache_replication_group.main.primary_endpoint_address}:${aws_elasticache_replication_group.main.port}"
        }) : { name = k, value = v }
      ]
      secrets = concat(
        [for name in local.api_secret_names : { name = name, valueFrom = "${each.value.secrets_arn}:${name}::" }],
        [{ name = "DATABASE_URL", valueFrom = "${each.value.db_secret_arn}:DB_URL::" }]
      )
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = each.value.log_group_name
          "awslogs-region"        = "us-east-1"
          "awslogs-stream-prefix" = "gunicorn"
        }
      }
      dependsOn = [{ containerName = "datadog-agent", condition = "START" }]
    }
  ])

  tags = {
    Name        = "spellbot-${each.key}-task-definition"
    Environment = each.key
  }
}
