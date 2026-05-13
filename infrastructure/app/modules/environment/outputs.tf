# Environment module outputs

output "secrets_arn" {
  description = "Secrets Manager secret ARN"
  value       = aws_secretsmanager_secret.spellbot.arn
}

output "db_secret_arn" {
  description = "Database secret ARN"
  value       = data.aws_secretsmanager_secret.db_password.arn
}

output "ssm_parameter_arn" {
  description = "SSM parameter ARN for image URI"
  value       = aws_ssm_parameter.spellbot_image_uri.arn
}

output "target_group_arn" {
  description = "ALB target group ARN"
  value       = aws_lb_target_group.spellbot.arn
}

output "certificate_arn" {
  description = "ACM certificate ARN"
  value       = aws_acm_certificate.spellbot.arn
}

output "certificate_validation_arn" {
  description = "ACM certificate validation ARN"
  value       = aws_acm_certificate_validation.spellbot.certificate_arn
}
