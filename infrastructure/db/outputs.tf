output "staging_database_name" {
  description = "Name of the staging database"
  value       = postgresql_database.staging_db.name
}

output "production_database_name" {
  description = "Name of the production database"
  value       = postgresql_database.production_db.name
}

output "staging_spellbot_user" {
  description = "Username for staging spellbot database user"
  value       = postgresql_role.staging_spellbot_user.name
}

output "production_spellbot_user" {
  description = "Username for production spellbot database user"
  value       = postgresql_role.production_spellbot_user.name
}

output "staging_password_secret_arn" {
  description = "ARN of the AWS Secrets Manager secret containing staging database credentials"
  value       = aws_secretsmanager_secret.staging_spellbot_password.arn
}

output "production_password_secret_arn" {
  description = "ARN of the AWS Secrets Manager secret containing production database credentials"
  value       = aws_secretsmanager_secret.production_spellbot_password.arn
}

output "staging_password_secret_name" {
  description = "Name of the AWS Secrets Manager secret containing staging database credentials"
  value       = aws_secretsmanager_secret.staging_spellbot_password.name
}

output "production_password_secret_name" {
  description = "Name of the AWS Secrets Manager secret containing production database credentials"
  value       = aws_secretsmanager_secret.production_spellbot_password.name
}

output "staging_connection_info" {
  description = "Complete connection information for staging database"
  value = {
    host     = var.db_host
    port     = var.db_port
    database = postgresql_database.staging_db.name
    username = postgresql_role.staging_spellbot_user.name
  }
  sensitive = false
}

output "production_connection_info" {
  description = "Complete connection information for production database"
  value = {
    host     = var.db_host
    port     = var.db_port
    database = postgresql_database.production_db.name
    username = postgresql_role.production_spellbot_user.name
  }
  sensitive = false
}
