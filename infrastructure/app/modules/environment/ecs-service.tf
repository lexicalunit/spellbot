# ECS Service for the environment

resource "aws_ecs_service" "spellbot" {
  name            = "spellbot-${var.env_name}"
  cluster         = var.ecs_cluster_id
  task_definition = aws_ecs_task_definition.spellbot.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  deployment_minimum_healthy_percent = var.deployment_minimum_healthy_percent
  deployment_maximum_percent         = var.deployment_maximum_percent

  dynamic "deployment_circuit_breaker" {
    for_each = var.enable_circuit_breaker ? [1] : []
    content {
      enable   = true
      rollback = true
    }
  }

  # Allow the bot to finish startup (cogs, gateway connect, initial task burst)
  # before the ALB starts evaluating the gunicorn target.
  health_check_grace_period_seconds = 180

  network_configuration {
    subnets          = var.public_subnets
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.spellbot.arn
    container_name   = "spellbot-gunicorn"
    container_port   = 80
  }

  depends_on = [
    aws_lb_listener_rule.spellbot
  ]

  tags = {
    Name        = "spellbot-${var.env_name}-service"
    Environment = var.env_name
  }
}
