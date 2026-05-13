# Environment module variables

variable "env_name" {
  description = "Environment name (e.g., prod, stage)"
  type        = string
}

variable "root_domain" {
  description = "Root domain for the application"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "public_subnets" {
  description = "List of public subnet IDs"
  type        = list(string)
}

variable "ecs_cluster_id" {
  description = "ECS cluster ID"
  type        = string
}

variable "ecs_task_execution_role_arn" {
  description = "ECS task execution role ARN"
  type        = string
}

variable "ecs_task_role_arn" {
  description = "ECS task role ARN"
  type        = string
}

variable "ecs_security_group_id" {
  description = "Security group ID for ECS tasks"
  type        = string
}

variable "alb_listener_arn" {
  description = "ALB HTTPS listener ARN"
  type        = string
}

variable "route53_zone_id" {
  description = "Route53 hosted zone ID"
  type        = string
}

variable "alb_dns_name" {
  description = "ALB DNS name for Route53 alias"
  type        = string
}

variable "alb_zone_id" {
  description = "ALB zone ID for Route53 alias"
  type        = string
}

variable "elasticache_endpoint" {
  description = "ElastiCache primary endpoint address"
  type        = string
}

variable "elasticache_port" {
  description = "ElastiCache port"
  type        = number
}

variable "redis_db" {
  description = "Redis database number"
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
}

variable "desired_count" {
  description = "Desired count for ECS service"
  type        = number
}

variable "deployment_minimum_healthy_percent" {
  description = "Minimum healthy percent during deployment"
  type        = number
}

variable "deployment_maximum_percent" {
  description = "Maximum percent during deployment"
  type        = number
}

variable "enable_circuit_breaker" {
  description = "Enable deployment circuit breaker"
  type        = bool
}

variable "listener_rule_priority" {
  description = "Priority for ALB listener rule"
  type        = number
}
