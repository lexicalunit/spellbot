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

# SpellBot Alerts
resource "datadog_monitor" "spellbot_tasks_not_running" {
  on_missing_data     = "default"
  require_full_window = false
  monitor_thresholds {
    critical = 1
  }
  name    = "SpellBot: Tasks are not running"
  tags    = ["service:spellbot", "env:prod"]
  type    = "log alert"
  query   = <<-EOT
    logs("environment:prod "starting task expire_inactive_games"").index("*").rollup("count").last("2h") < 1
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
  tags    = ["service:spellbot", "env:prod"]
  query   = <<-EOT
    logs("environment:prod -@aws.awslogs.logStream:datadog/datadog-agent/* -"ELB-HealthChecker" (error OR status:error)").index("*").rollup("count").last("5m") > 1
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

resource "datadog_monitor" "SpellBot_SpellTable_create_game_issues" {
  include_tags        = false
  on_missing_data     = "default"
  require_full_window = false
  monitor_thresholds {
    critical = 6000000000
  }
  name    = "SpellBot: SpellTable create game issues"
  type    = "trace-analytics alert"
  tags    = ["env:prod", "service:spellbot"]
  query   = <<-EOT
    trace-analytics("env:prod service:spellbot operation_name:spellbot.client.create_game_link @link_service:SPELLTABLE").index("trace-search", "djm-search").rollup("avg", "@duration").last("5m") > 6000000000
  EOT
  message = "@${var.alert_email}"
}

# ECS Alerts
resource "datadog_monitor" "SpellBot_ECS_Tasks_Failed_to_Start_Successfully" {
  evaluation_delay       = 900
  groupby_simple_monitor = false
  new_group_delay        = 60
  on_missing_data        = "default"
  require_full_window    = false
  monitor_thresholds {
    critical = 0
  }
  name    = "SpellBot: ECS Tasks Failed to Start Successfully"
  type    = "event-v2 alert"
  tags    = ["integration:amazon_ecs"]
  query   = <<-EOT
    events("source:amazon_ecs "unable to consistently start tasks successfully"").rollup("count").by("servicename,clustername,aws_account,region").last("5m") > 0
  EOT
  message = <<-EOT
    {{#is_alert}}
    ECS service:{{servicename.name}} (cluster:{{clustername.name}}) was unable to start successfully.
    {{/is_alert}}

    To investigate further, view the affected service in the [ECS Explorer](/orchestration/explorer/ecsService?query=ecs_service:{{servicename.name}}+ecs_cluster:{{clustername.name}}+aws_account:{{aws_account.name}}+region:{{region.name}})

    @${var.alert_email}
  EOT
}

resource "datadog_monitor" "AWS_ECS_Memory_Reservation_Exceeds_Threshold" {
  escalation_message   = ""
  evaluation_delay     = 900
  new_group_delay      = 60
  on_missing_data      = "show_no_data"
  renotify_interval    = 1440
  renotify_occurrences = 0
  renotify_statuses    = ["alert"]
  require_full_window  = false
  monitor_thresholds {
    critical = 90
    warning  = 80
  }
  name    = "[AWS] ECS Memory Reservation Exceeds Threshold"
  type    = "query alert"
  tags    = ["integration:amazon_ecs"]
  query   = <<-EOT
    min(last_30m):sum:aws.ecs.memory_utilization{*} by {clustername,aws_account,region}.weighted() > 90
  EOT
  message = <<-EOT
    {{#is_warning}}
    Memory Reservation for ECS cluster {{clustername.name}} is approaching the threshold of {{threshold}}%
    {{/is_warning}}

    {{#is_alert}}
    Memory Reservation for ECS cluster {{clustername.name}} has exceeded the threshold of {{threshold}}%
    {{/is_alert}}

    To investigate further, view the affected cluster in the [ECS Explorer](/orchestration/explorer/ecsCluster?query=ecs_cluster:{{clustername.name}}+aws_account:{{aws_account.name}}+region:{{region.name}})

    @${var.alert_email}
  EOT
}

resource "datadog_monitor" "ECS_Fargate_AWS_ECS_Task_CPU_utilization_is_high" {
  new_group_delay     = 300
  on_missing_data     = "default"
  require_full_window = false
  monitor_thresholds {
    critical = 80
  }
  name    = "[ECS Fargate] AWS ECS Task CPU utilization is high"
  type    = "query alert"
  tags    = ["integration:ecs_fargate"]
  query   = <<-EOT
    avg(last_15m):sum:ecs.fargate.cpu.usage{*} by {ecs_cluster,task_arn,ecs_service} / sum:ecs.fargate.cpu.task.limit{*} by {ecs_cluster,task_arn,ecs_service} * 100 > 80
  EOT
  message = <<-EOT
    {{#is_warning}}
    AWS ECS Task {{task_arn.name}} in service {{ecs_service.name}} (cluster {{ecs_cluster.name}}) is approaching CPU Utilization threshold
    {{/is_warning}}

    {{#is_alert}}
    AWS ECS Task {{task_arn.name}} in service {{ecs_service.name}} (cluster {{ecs_cluster.name}}) has crossed CPU Utilization threshold
    {{/is_alert}}

    To investigate further, view the affected task in the [ECS Explorer](/orchestration/explorer/ecsTask?inspect={{task_arn.name}})

    @${var.alert_email}
  EOT
}

resource "datadog_monitor" "AWS_ECS_Running_Task_Count_differs_from_Desired_Count" {
  evaluation_delay    = 900
  new_group_delay     = 60
  require_full_window = false
  monitor_thresholds {
    critical = 1
  }
  name    = "[AWS] ECS Running Task Count differs from Desired Count"
  type    = "query alert"
  tags    = ["integration:amazon_ecs"]
  query   = <<-EOT
    min(last_1h):sum:aws.ecs.service.desired{environment:prod} by {servicename,clustername,aws_account,region} - sum:aws.ecs.service.running{environment:prod} by {servicename,clustername,aws_account,region} >= 1
  EOT
  message = <<-EOT
    {{#is_alert}}
    ECS Running Task Count is not equal to Desired Task Count for {{servicename.name}} in cluster {{clustername.name}}.
    {{/is_alert}}

    To investigate further, view the affected service in the [ECS Explorer](/orchestration/explorer/ecsService?query=ecs_service:{{servicename.name}}+ecs_cluster:{{clustername.name}}+aws_account:{{aws_account.name}}+region:{{region.name}})

    @${var.alert_email}
  EOT
}

# Dashboards
resource "datadog_dashboard" "spellbot_create_game_link_dashboard" {
  title       = "Avg of duration of create_game_link"
  description = "Average duration of create_game_link calls"
  layout_type = "ordered"
  widget {
    timeseries_definition {
      request {
        apm_query {
          index        = "*"
          search_query = "env:prod service:spellbot operation_name:spellbot.client.create_game_link @link_service:SPELLTABLE"
          compute_query {
            aggregation = "avg"
            facet       = "@duration"
            interval    = 1800000
          }
        }
      }
      live_span = "1w"
    }
  }
}
