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
  message = <<-EOT
    {{#is_alert}}
    @${var.alert_email}
    {{/is_alert}}
  EOT
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
    logs("environment:prod -@aws.awslogs.logStream:datadog/datadog-agent/* -404 -\"ELB-HealthChecker\" -\"Error handling request from\" -\"raise ex\" -\"raise LineTooLong\" (env:error OR status:error OR raise)").index("*").rollup("count").last("5m") > 1
  EOT
  message = <<-EOT
    {{#is_alert}}
    @${var.alert_email}
    {{/is_alert}}
  EOT
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
  message = <<-EOT
    {{#is_alert}}
    @${var.alert_email}
    {{/is_alert}}
  EOT
}

resource "datadog_monitor" "SpellBot_SpellTable_create_game_issues" {
  include_tags        = false
  on_missing_data     = "default"
  require_full_window = false
  monitor_thresholds {
    critical = 8000000000
  }
  name    = "SpellBot: SpellTable create game issues"
  type    = "trace-analytics alert"
  tags    = ["env:prod", "service:spellbot"]
  query   = <<-EOT
    trace-analytics("env:prod service:spellbot operation_name:spellbot.client.create_game_link @link_service:SPELLTABLE").index("trace-search", "djm-search").rollup("avg", "@duration").last("5m") > 8000000000
  EOT
  message = <<-EOT
    {{#is_alert}}
    @${var.alert_email}
    {{/is_alert}}
  EOT
}

resource "datadog_monitor" "spellbot_apm_trace_errors" {
  on_missing_data     = "default"
  require_full_window = false
  monitor_thresholds {
    critical = 1
  }
  name    = "SpellBot: APM Trace Errors"
  type    = "trace-analytics alert"
  tags    = ["env:prod", "service:spellbot"]
  query   = <<-EOT
    trace-analytics("env:prod service:spellbot -status:ok").index("trace-search", "djm-search").rollup("count").last("5m") > 1
  EOT
  message = <<-EOT
    {{#is_alert}}
    SpellBot is experiencing an elevated number of APM trace errors in the last 5 minutes.

    @${var.alert_email}
    {{/is_alert}}
  EOT
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

    To investigate further, view the affected service in the [ECS Explorer](/orchestration/explorer/ecsService?query=ecs_service:{{servicename.name}}+ecs_cluster:{{clustername.name}}+aws_account:{{aws_account.name}}+region:{{region.name}})

    @${var.alert_email}
    {{/is_alert}}
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

    To investigate further, view the affected cluster in the [ECS Explorer](/orchestration/explorer/ecsCluster?query=ecs_cluster:{{clustername.name}}+aws_account:{{aws_account.name}}+region:{{region.name}})

    @${var.alert_email}
    {{/is_warning}}
    {{#is_alert}}
    Memory Reservation for ECS cluster {{clustername.name}} has exceeded the threshold of {{threshold}}%

    To investigate further, view the affected cluster in the [ECS Explorer](/orchestration/explorer/ecsCluster?query=ecs_cluster:{{clustername.name}}+aws_account:{{aws_account.name}}+region:{{region.name}})

    @${var.alert_email}
    {{/is_alert}}
  EOT
}

resource "datadog_monitor" "ECS_Fargate_AWS_ECS_Task_CPU_utilization_is_high" {
  evaluation_delay    = 900
  on_missing_data     = "default"
  require_full_window = false
  monitor_thresholds {
    critical = 80
  }
  name    = "[ECS Fargate] AWS ECS Task CPU utilization is high"
  type    = "query alert"
  tags    = ["integration:ecs_fargate"]
  query   = <<-EOT
    avg(last_1h):sum:aws.ecs.cpuutilization{*}.weighted() > 80
  EOT
  message = <<-EOT
    {{#is_warning}}
    AWS ECS Task {{task_arn.name}} in service {{ecs_service.name}} (cluster {{ecs_cluster.name}}) is approaching CPU Utilization threshold

    To investigate further, view the affected task in the [ECS Explorer](/orchestration/explorer/ecsTask?inspect={{task_arn.name}})

    @${var.alert_email}
    {{/is_warning}}
    {{#is_alert}}
    AWS ECS Task {{task_arn.name}} in service {{ecs_service.name}} (cluster {{ecs_cluster.name}}) has crossed CPU Utilization threshold

    To investigate further, view the affected task in the [ECS Explorer](/orchestration/explorer/ecsTask?inspect={{task_arn.name}})

    @${var.alert_email}
    {{/is_alert}}
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

    To investigate further, view the affected service in the [ECS Explorer](/orchestration/explorer/ecsService?query=ecs_service:{{servicename.name}}+ecs_cluster:{{clustername.name}}+aws_account:{{aws_account.name}}+region:{{region.name}})

    @${var.alert_email}
    {{/is_alert}}
  EOT
}

resource "datadog_monitor" "SpellBot_No_traces" {
  no_data_timeframe   = 10
  require_full_window = false
  monitor_thresholds {
    critical = 0
  }
  name    = "SpellBot: No traces"
  type    = "query alert"
  tags    = ["service:spellbot", "env:prod"]
  query   = <<-EOT
    sum(last_5m):sum:trace.interaction.hits{env:prod,service:spellbot,span.kind:internal}.as_rate() <= 0
  EOT
  message = <<-EOT
    {{#is_alert}}
    @${var.alert_email}
    {{/is_alert}}
  EOT
}

# RDS Database Alerts
resource "datadog_monitor" "rds_cpu_utilization" {
  evaluation_delay    = 900
  on_missing_data     = "default"
  require_full_window = false
  monitor_thresholds {
    critical = 90
    warning  = 80
  }
  name    = "[RDS] CPU Utilization High"
  type    = "query alert"
  tags    = ["integration:amazon_rds", "env:prod"]
  query   = <<-EOT
    avg(last_15m):avg:aws.rds.cpuutilization{dbinstanceidentifier:spellbot*} by {dbinstanceidentifier} > 90
  EOT
  message = <<-EOT
    {{#is_warning}}
    RDS instance {{dbinstanceidentifier.name}} CPU utilization is approaching {{threshold}}%.
    @${var.alert_email}
    {{/is_warning}}
    {{#is_alert}}
    RDS instance {{dbinstanceidentifier.name}} CPU utilization has exceeded {{threshold}}%.
    @${var.alert_email}
    {{/is_alert}}
  EOT
}

resource "datadog_monitor" "rds_write_latency" {
  evaluation_delay    = 900
  on_missing_data     = "default"
  require_full_window = false
  monitor_thresholds {
    critical = 0.1
    warning  = 0.05
  }
  name    = "[RDS] Write Latency High"
  type    = "query alert"
  tags    = ["integration:amazon_rds", "env:prod"]
  query   = <<-EOT
    avg(last_15m):avg:aws.rds.write_latency{dbinstanceidentifier:spellbot*} by {dbinstanceidentifier} > 0.1
  EOT
  message = <<-EOT
    {{#is_warning}}
    RDS instance {{dbinstanceidentifier.name}} write latency is elevated ({{value}}s).
    @${var.alert_email}
    {{/is_warning}}
    {{#is_alert}}
    RDS instance {{dbinstanceidentifier.name}} write latency is critically high ({{value}}s).
    @${var.alert_email}
    {{/is_alert}}
  EOT
}

resource "datadog_monitor" "rds_read_latency" {
  evaluation_delay    = 900
  on_missing_data     = "default"
  require_full_window = false
  monitor_thresholds {
    critical = 0.1
    warning  = 0.05
  }
  name    = "[RDS] Read Latency High"
  type    = "query alert"
  tags    = ["integration:amazon_rds", "env:prod"]
  query   = <<-EOT
    avg(last_15m):avg:aws.rds.read_latency{dbinstanceidentifier:spellbot*} by {dbinstanceidentifier} > 0.1
  EOT
  message = <<-EOT
    {{#is_warning}}
    RDS instance {{dbinstanceidentifier.name}} read latency is elevated ({{value}}s).
    @${var.alert_email}
    {{/is_warning}}
    {{#is_alert}}
    RDS instance {{dbinstanceidentifier.name}} read latency is critically high ({{value}}s).
    @${var.alert_email}
    {{/is_alert}}
  EOT
}

resource "datadog_monitor" "rds_database_connections" {
  evaluation_delay    = 900
  on_missing_data     = "default"
  require_full_window = false
  monitor_thresholds {
    critical = 100
    warning  = 80
  }
  name    = "[RDS] Database Connections High"
  type    = "query alert"
  tags    = ["integration:amazon_rds", "env:prod"]
  query   = <<-EOT
    avg(last_15m):avg:aws.rds.database_connections{dbinstanceidentifier:spellbot*} by {dbinstanceidentifier} > 100
  EOT
  message = <<-EOT
    {{#is_warning}}
    RDS instance {{dbinstanceidentifier.name}} has {{value}} database connections (approaching limit).
    @${var.alert_email}
    {{/is_warning}}
    {{#is_alert}}
    RDS instance {{dbinstanceidentifier.name}} has {{value}} database connections (critically high).
    @${var.alert_email}
    {{/is_alert}}
  EOT
}

resource "datadog_monitor" "rds_swap_usage" {
  evaluation_delay    = 900
  on_missing_data     = "default"
  require_full_window = false
  monitor_thresholds {
    critical = 524288000
    warning  = 314572800
  }
  name    = "[RDS] Swap Usage High"
  type    = "query alert"
  tags    = ["integration:amazon_rds", "env:prod"]
  query   = <<-EOT
    avg(last_15m):avg:aws.rds.swap_usage{dbinstanceidentifier:spellbot*} by {dbinstanceidentifier} > 524288000
  EOT
  message = <<-EOT
    {{#is_warning}}
    RDS instance {{dbinstanceidentifier.name}} swap usage is elevated (300MB+). This may indicate memory pressure.
    @${var.alert_email}
    {{/is_warning}}
    {{#is_alert}}
    RDS instance {{dbinstanceidentifier.name}} swap usage is critically high (500MB+). Performance may be degraded.
    @${var.alert_email}
    {{/is_alert}}
  EOT
}

resource "datadog_monitor" "rds_deadlocks" {
  evaluation_delay    = 900
  on_missing_data     = "default"
  require_full_window = false
  monitor_thresholds {
    critical = 1
  }
  name    = "[RDS] Deadlocks Detected"
  type    = "query alert"
  tags    = ["integration:amazon_rds", "env:prod"]
  query   = <<-EOT
    sum(last_5m):sum:aws.rds.deadlocks{dbinstanceidentifier:spellbot*} by {dbinstanceidentifier} > 1
  EOT
  message = <<-EOT
    {{#is_alert}}
    RDS instance {{dbinstanceidentifier.name}} has detected {{value}} deadlocks in the last 5 minutes.
    @${var.alert_email}
    {{/is_alert}}
  EOT
}

resource "datadog_monitor" "rds_free_local_storage" {
  evaluation_delay    = 900
  on_missing_data     = "default"
  require_full_window = false
  monitor_thresholds {
    critical = 4294967296
    warning  = 5368709120
  }
  name    = "[RDS] Free Local Storage Low"
  type    = "query alert"
  tags    = ["integration:amazon_rds", "env:prod"]
  query   = <<-EOT
    avg(last_15m):avg:aws.rds.free_local_storage{dbinstanceidentifier:spellbot*} by {dbinstanceidentifier} < 4294967296
  EOT
  message = <<-EOT
    {{#is_warning}}
    RDS instance {{dbinstanceidentifier.name}} has less than 5GB of free local storage.
    @${var.alert_email}
    {{/is_warning}}
    {{#is_alert}}
    RDS instance {{dbinstanceidentifier.name}} has less than 4GB of free local storage. Immediate attention required.
    @${var.alert_email}
    {{/is_alert}}
  EOT
}

resource "datadog_monitor" "rds_dbload" {
  evaluation_delay    = 900
  on_missing_data     = "default"
  require_full_window = false
  monitor_thresholds {
    critical = 4
    warning  = 2
  }
  name    = "[RDS] Database Load High"
  type    = "query alert"
  tags    = ["integration:amazon_rds", "env:prod"]
  query   = <<-EOT
    avg(last_15m):avg:aws.rds.dbload{dbinstanceidentifier:spellbot*} by {dbinstanceidentifier} > 4
  EOT
  message = <<-EOT
    {{#is_warning}}
    RDS instance {{dbinstanceidentifier.name}} database load is elevated ({{value}} active sessions).
    @${var.alert_email}
    {{/is_warning}}
    {{#is_alert}}
    RDS instance {{dbinstanceidentifier.name}} database load is critically high ({{value}} active sessions).
    @${var.alert_email}
    {{/is_alert}}
  EOT
}

resource "datadog_monitor" "rds_freeable_memory" {
  evaluation_delay    = 900
  on_missing_data     = "default"
  require_full_window = false
  monitor_thresholds {
    critical = 268435456
    warning  = 536870912
  }
  name    = "[RDS] Freeable Memory Low"
  type    = "query alert"
  tags    = ["integration:amazon_rds", "env:prod"]
  query   = <<-EOT
    avg(last_15m):avg:aws.rds.freeable_memory{dbinstanceidentifier:spellbot*} by {dbinstanceidentifier} < 268435456
  EOT
  message = <<-EOT
    {{#is_warning}}
    RDS instance {{dbinstanceidentifier.name}} has less than 512MB of freeable memory.
    @${var.alert_email}
    {{/is_warning}}
    {{#is_alert}}
    RDS instance {{dbinstanceidentifier.name}} has less than 256MB of freeable memory. Performance may be severely impacted.
    @${var.alert_email}
    {{/is_alert}}
  EOT
}

resource "datadog_monitor" "rds_disk_queue_depth" {
  evaluation_delay    = 900
  on_missing_data     = "default"
  require_full_window = false
  monitor_thresholds {
    critical = 64
    warning  = 32
  }
  name    = "[RDS] Disk Queue Depth High"
  type    = "query alert"
  tags    = ["integration:amazon_rds", "env:prod"]
  query   = <<-EOT
    avg(last_15m):avg:aws.rds.disk_queue_depth{dbinstanceidentifier:spellbot*} by {dbinstanceidentifier} > 64
  EOT
  message = <<-EOT
    {{#is_warning}}
    RDS instance {{dbinstanceidentifier.name}} disk queue depth is elevated ({{value}}). I/O operations may be queuing up.
    @${var.alert_email}
    {{/is_warning}}
    {{#is_alert}}
    RDS instance {{dbinstanceidentifier.name}} disk queue depth is critically high ({{value}}). I/O bottleneck detected.
    @${var.alert_email}
    {{/is_alert}}
  EOT
}

# Dashboards
resource "datadog_dashboard" "spellbot_dashboard" {
  title       = "SpellBot Dashboard"
  description = "Metrics and performance dashboard for SpellBot"
  layout_type = "ordered"

  # --- Interaction Performance ---
  widget {
    timeseries_definition {
      title = "Interaction Latency by Command (avg)"
      request {
        apm_query {
          index        = "*"
          search_query = "env:prod service:spellbot resource_name:spellbot.interactions.* retained_by:*"
          group_by {
            facet = "resource_name"
            limit = 10
            sort_query {
              aggregation = "avg"
              facet       = "@duration"
              order       = "desc"
            }
          }
          compute_query {
            aggregation = "avg"
            facet       = "@duration"
            interval    = 3600000
          }
        }
      }
    }
  }

  widget {
    timeseries_definition {
      title = "Interactions per Hour by Type"
      request {
        apm_query {
          index        = "*"
          search_query = "env:prod service:spellbot resource_name:spellbot.interactions.* retained_by:*"
          group_by {
            facet = "resource_name"
            limit = 10
            sort_query {
              aggregation = "count"
              order       = "desc"
            }
          }
          compute_query {
            aggregation = "count"
            interval    = 3600000
          }
        }
      }
    }
  }

  # --- Discord API Performance ---
  widget {
    timeseries_definition {
      title = "Discord API Calls by Status"
      request {
        apm_query {
          index        = "*"
          search_query = "env:prod service:discord retained_by:*"
          group_by {
            facet = "status"
            limit = 10
            sort_query {
              aggregation = "count"
              order       = "desc"
            }
          }
          compute_query {
            aggregation = "count"
            interval    = 3600000
          }
        }
      }
    }
  }

  widget {
    timeseries_definition {
      title = "Discord API Latency (avg)"
      request {
        apm_query {
          index        = "*"
          search_query = "env:prod service:discord retained_by:*"
          group_by {
            facet = "resource_name"
            limit = 10
            sort_query {
              aggregation = "avg"
              facet       = "@duration"
              order       = "desc"
            }
          }
          compute_query {
            aggregation = "avg"
            facet       = "@duration"
            interval    = 3600000
          }
        }
      }
    }
  }

  # --- Database Performance ---
  widget {
    timeseries_definition {
      title = "Postgres Query Latency (avg)"
      request {
        formula {
          formula_expression = "query1"
        }
        query {
          event_query {
            name        = "query1"
            data_source = "spans"
            search {
              query = "env:prod @base_service:spellbot @db.system:postgresql"
            }
            indexes = ["*"]
            group_by {
              facet = "resource_name"
              limit = 10
              sort {
                aggregation = "avg"
                metric      = "@duration"
                order       = "desc"
              }
            }
            compute {
              aggregation = "avg"
              metric      = "@duration"
              interval    = 3600000
            }
          }
        }
      }
    }
  }

  widget {
    timeseries_definition {
      title = "Postgres Queries per Hour"
      request {
        formula {
          formula_expression = "query1"
        }
        query {
          event_query {
            name        = "query1"
            data_source = "spans"
            search {
              query = "env:prod @base_service:spellbot @db.system:postgresql"
            }
            indexes = ["*"]
            group_by {
              facet = "resource_name"
              limit = 10
              sort {
                aggregation = "count"
                order       = "desc"
              }
            }
            compute {
              aggregation = "count"
              interval    = 3600000
            }
          }
        }
      }
    }
  }

  # --- Error Tracking ---
  widget {
    timeseries_definition {
      title = "Errors by Service"
      request {
        apm_query {
          index        = "*"
          search_query = "env:prod status:error retained_by:*"
          group_by {
            facet = "service"
            limit = 10
            sort_query {
              aggregation = "count"
              order       = "desc"
            }
          }
          compute_query {
            aggregation = "count"
            interval    = 3600000
          }
        }
      }
    }
  }

  widget {
    timeseries_definition {
      title = "Warnings (Expected Errors)"
      request {
        formula {
          formula_expression = "query1"
        }
        query {
          event_query {
            name        = "query1"
            data_source = "spans"
            search {
              query = "env:prod service:spellbot"
            }
            indexes = ["*"]
            group_by {
              facet = "@warning.type"
              limit = 10
              sort {
                aggregation = "count"
                order       = "desc"
              }
            }
            compute {
              aggregation = "count"
              interval    = 3600000
            }
          }
        }
      }
    }
  }

  # --- Game Link Services ---
  widget {
    timeseries_definition {
      title = "Game Link Creation by Service"
      request {
        apm_query {
          index        = "*"
          search_query = "env:prod service:spellbot operation_name:spellbot.client.create_game_link retained_by:*"
          group_by {
            facet = "@link_service"
            limit = 10
            sort_query {
              aggregation = "count"
              order       = "desc"
            }
          }
          compute_query {
            aggregation = "count"
            interval    = 3600000
          }
        }
      }
    }
  }

  widget {
    timeseries_definition {
      title = "Game Link Creation Latency by Service (avg)"
      request {
        apm_query {
          index        = "*"
          search_query = "env:prod service:spellbot operation_name:spellbot.client.create_game_link retained_by:*"
          group_by {
            facet = "@link_service"
          }
          compute_query {
            aggregation = "avg"
            facet       = "@duration"
            interval    = 1800000
          }
        }
      }
    }
  }

  # --- Web API ---
  widget {
    timeseries_definition {
      title = "Web API Requests by Endpoint"
      request {
        formula {
          formula_expression = "query1"
        }
        query {
          event_query {
            name        = "query1"
            data_source = "spans"
            search {
              query = "env:prod service:spellapi"
            }
            indexes = ["*"]
            group_by {
              facet = "resource_name"
              limit = 10
              sort {
                aggregation = "count"
                order       = "desc"
              }
            }
            compute {
              aggregation = "count"
              interval    = 3600000
            }
          }
        }
      }
    }
  }
}

# Queries
resource "datadog_monitor" "Abnormal_change_in_p75_latency_for_postgres" {
  name                = "Abnormal change in p75 latency for postgres"
  type                = "query alert"
  query               = <<EOT
avg(last_12h):anomalies(p75:trace.postgres.query{env:prod,service:postgres,span.kind:client}, 'agile', 2, direction='both', interval=120, alert_window='last_30m', count_default_zero='true', seasonality='hourly') >= 1
EOT
  message             = <<-EOT
    {{#is_alert}}
    service:postgres has an abnormal change in latency. The 75th percentile latency has deviated significantly.

    @amy@lexicalunit.com
    {{/is_alert}}
  EOT
  tags                = ["service:postgres", "env:prod"]
  include_tags        = false
  on_missing_data     = "show_no_data"
  require_full_window = false
  monitor_thresholds {
    critical = 1
  }
  monitor_threshold_windows {
    recovery_window = "last_15m"
    trigger_window  = "last_30m"
  }
}
