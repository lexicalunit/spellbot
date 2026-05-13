# Environment modules - stage and prod

module "stage" {
  source = "./modules/environment"

  env_name    = "stage"
  root_domain = var.root_domain

  # VPC
  vpc_id         = module.vpc.vpc_id
  public_subnets = module.vpc.public_subnets

  # ECS
  ecs_cluster_id              = aws_ecs_cluster.main.id
  ecs_task_execution_role_arn = aws_iam_role.ecs_task_execution_role.arn
  ecs_task_role_arn           = aws_iam_role.ecs_task_role.arn
  ecs_security_group_id       = aws_security_group.ecs_tasks.id

  # ALB
  alb_listener_arn = aws_lb_listener.https.arn
  alb_dns_name     = aws_lb.main.dns_name
  alb_zone_id      = aws_lb.main.zone_id

  # Route53
  route53_zone_id = aws_route53_zone.main.zone_id

  # ElastiCache
  elasticache_endpoint = aws_elasticache_replication_group.main.primary_endpoint_address
  elasticache_port     = aws_elasticache_replication_group.main.port

  # Environment-specific settings
  redis_db                           = "1"
  log_retention_days                 = 1
  desired_count                      = 0
  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100
  enable_circuit_breaker             = false
  listener_rule_priority             = 200
}

module "prod" {
  source = "./modules/environment"

  env_name    = "prod"
  root_domain = var.root_domain

  # VPC
  vpc_id         = module.vpc.vpc_id
  public_subnets = module.vpc.public_subnets

  # ECS
  ecs_cluster_id              = aws_ecs_cluster.main.id
  ecs_task_execution_role_arn = aws_iam_role.ecs_task_execution_role.arn
  ecs_task_role_arn           = aws_iam_role.ecs_task_role.arn
  ecs_security_group_id       = aws_security_group.ecs_tasks.id

  # ALB
  alb_listener_arn = aws_lb_listener.https.arn
  alb_dns_name     = aws_lb.main.dns_name
  alb_zone_id      = aws_lb.main.zone_id

  # Route53
  route53_zone_id = aws_route53_zone.main.zone_id

  # ElastiCache
  elasticache_endpoint = aws_elasticache_replication_group.main.primary_endpoint_address
  elasticache_port     = aws_elasticache_replication_group.main.port

  # Environment-specific settings
  redis_db                           = "0"
  log_retention_days                 = 5
  desired_count                      = 1
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  enable_circuit_breaker             = true
  listener_rule_priority             = 100
}
