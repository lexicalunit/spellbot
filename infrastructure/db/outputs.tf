output "stage_database_name" {
  description = "Name of the stage database"
  value       = postgresql_database.stage_db.name
}

output "prod_database_name" {
  description = "Name of the prod database"
  value       = postgresql_database.prod_db.name
}

output "stage_spellbot_user" {
  description = "Username for stage spellbot database user"
  value       = postgresql_role.stage_spellbot_user.name
}

output "prod_spellbot_user" {
  description = "Username for prod spellbot database user"
  value       = postgresql_role.prod_spellbot_user.name
}

output "stage_password_secret_arn" {
  description = "ARN of the AWS Secrets Manager secret containing stage database credentials"
  value       = aws_secretsmanager_secret.stage_spellbot_password.arn
}

output "prod_password_secret_arn" {
  description = "ARN of the AWS Secrets Manager secret containing prod database credentials"
  value       = aws_secretsmanager_secret.prod_spellbot_password.arn
}

output "stage_password_secret_name" {
  description = "Name of the AWS Secrets Manager secret containing stage database credentials"
  value       = aws_secretsmanager_secret.stage_spellbot_password.name
}

output "prod_password_secret_name" {
  description = "Name of the AWS Secrets Manager secret containing prod database credentials"
  value       = aws_secretsmanager_secret.prod_spellbot_password.name
}

output "stage_connection_info" {
  description = "Complete connection information for stage database"
  value = {
    host     = var.db_host
    port     = var.db_port
    database = postgresql_database.stage_db.name
    username = postgresql_role.stage_spellbot_user.name
  }
  sensitive = false
}

output "prod_connection_info" {
  description = "Complete connection information for prod database"
  value = {
    host     = var.db_host
    port     = var.db_port
    database = postgresql_database.prod_db.name
    username = postgresql_role.prod_spellbot_user.name
  }
  sensitive = false
}
