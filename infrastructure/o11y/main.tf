terraform {
  required_version = ">= 1.11.4"

  required_providers {
    datadog = {
      source  = "DataDog/datadog"
      version = "~> 3.73"
    }
  }
  backend "s3" {
    bucket = "spellbot-terraform-state"
    key    = "spellbot-o11y"
    region = "us-east-2"
  }
}

provider "datadog" {
  api_key = var.datadog_api_key
  app_key = var.datadog_app_key
}

resource "datadog_monitor" "spellbot_tasks_not_running" {
  on_missing_data     = "default"
  require_full_window = false
  monitor_thresholds {
    critical = 1
  }
  name    = "SpellBot: Tasks are not running"
  tags    = ["service:spellbot"]
  type    = "log alert"
  query   = <<-EOT
    logs("starting task expire_inactive_games").index("*").rollup("count").last("2h") < 1
  EOT
  message = "@${var.alert_email}"
}

resource "datadog_monitor" "spellbot_application_error" {
  enable_logs_sample     = true
  groupby_simple_monitor = false
  on_missing_data        = "default"
  require_full_window    = false
  monitor_thresholds {
    critical = 1
  }
  name    = "SpellBot: Application error: {{log.message}}"
  type    = "log alert"
  tags    = ["service:spellbot"]
  query   = <<-EOT
    logs("-@aws.awslogs.logStream:datadog/datadog-agent/* -"ELB-HealthChecker" (error OR status:error)").index("*").rollup("count").last("5m") > 1
  EOT
  message = "@${var.alert_email}"
}

resource "datadog_monitor" "spellbot_no_data_prod" {
  require_full_window = false
  monitor_thresholds {
    critical = 0
  }
  name    = "SpellBot: No data for postgres on env:prod"
  type    = "query alert"
  tags    = ["service:postgres", "env:prod"]
  query   = <<-EOT
    sum(last_15m):sum:trace.postgres.query.hits{env:prod,service:postgres,span.kind:client}.as_rate() <= 0
  EOT
  message = "@${var.alert_email}"
}

resource "datadog_monitor" "SpellBot_ECS_Tasks_Failed_to_Start_Successfully" {
  evaluation_delay       = 900
  groupby_simple_monitor = false
  new_group_delay        = 60
  on_missing_data        = "default"
  require_full_window    = false
  monitor_thresholds {
    critical = 1
  }
  name    = "SpellBot: ECS Tasks Failed to Start Successfully"
  type    = "event-v2 alert"
  tags    = ["integration:amazon_ecs"]
  query   = <<-EOT
    events("source:amazon_ecs "unable to consistently start tasks successfully"").rollup("count").by("servicename,clustername,aws_account,region").last("5m") > 1
  EOT
  message = <<-EOT
    {{#is_alert}}
    ECS service:{{servicename.name}} (cluster:{{clustername.name}}) was unable to start successfully.
    {{/is_alert}}

    To investigate further, view the affected service in the [ECS Explorer](/orchestration/explorer/ecsService?query=ecs_service:{{servicename.name}}+ecs_cluster:{{clustername.name}}+aws_account:{{aws_account.name}}+region:{{region.name}})

    @${var.alert_email}
  EOT
}
