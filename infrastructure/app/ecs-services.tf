# ECS Services

locals {
  ecs_service_config = {
    prod = {
      desired_count                      = 1
      deployment_minimum_healthy_percent = 100
      deployment_maximum_percent         = 200
      # Circuit breaker for prod: rollback automatically if new tasks fail
      enable_circuit_breaker = true
    }
    stage = {
      desired_count                      = 0
      deployment_minimum_healthy_percent = 0
      deployment_maximum_percent         = 100
      enable_circuit_breaker             = false
    }
  }
}

resource "aws_ecs_service" "spellbot" {
  for_each = local.env_names

  name            = "spellbot-${each.key}"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.spellbot[each.key].arn
  desired_count   = local.ecs_service_config[each.key].desired_count
  launch_type     = "FARGATE"

  deployment_minimum_healthy_percent = local.ecs_service_config[each.key].deployment_minimum_healthy_percent
  deployment_maximum_percent         = local.ecs_service_config[each.key].deployment_maximum_percent

  dynamic "deployment_circuit_breaker" {
    for_each = local.ecs_service_config[each.key].enable_circuit_breaker ? [1] : []
    content {
      enable   = true
      rollback = true
    }
  }

  # Allow the bot to finish startup (cogs, gateway connect, initial task burst)
  # before the ALB starts evaluating the gunicorn target.
  health_check_grace_period_seconds = 180

  network_configuration {
    subnets          = module.vpc.public_subnets
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.spellbot[each.key].arn
    container_name   = "spellbot-gunicorn"
    container_port   = 80
  }

  depends_on = [
    aws_lb_listener.https,
    aws_lb_listener_rule.spellbot
  ]

  tags = {
    Name        = "spellbot-${each.key}-service"
    Environment = each.key
  }
}
