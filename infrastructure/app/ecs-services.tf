# ECS Service - prod
resource "aws_ecs_service" "spellbot_prod" {
  name            = "spellbot-prod"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.spellbot_prod.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  # Deployment configuration - no duplicates allowed (0% min, 100% max)
  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100

  network_configuration {
    subnets          = module.vpc.public_subnets
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.prod.arn
    container_name   = "spellbot-gunicorn"
    container_port   = 80
  }

  depends_on = [
    aws_lb_listener.https,
    aws_lb_listener_rule.prod
  ]

  tags = {
    Name        = "spellbot-prod-service"
    Environment = "prod"
  }
}

# ECS Service - stage
resource "aws_ecs_service" "spellbot_stage" {
  name            = "spellbot-stage"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.spellbot_stage.arn
  desired_count   = 0
  launch_type     = "FARGATE"

  # Deployment configuration - no duplicates allowed (0% min, 100% max)
  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100

  network_configuration {
    subnets          = module.vpc.public_subnets
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.stage.arn
    container_name   = "spellbot-gunicorn"
    container_port   = 80
  }

  depends_on = [
    aws_lb_listener.https,
    aws_lb_listener_rule.stage
  ]

  tags = {
    Name        = "spellbot-stage-service"
    Environment = "stage"
  }
}
