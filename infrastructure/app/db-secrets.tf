# Data sources for database secrets created by the db module
data "aws_secretsmanager_secret" "staging_db_password" {
  name = "spellbot/staging/db-details"
}

data "aws_secretsmanager_secret" "production_db_password" {
  name = "spellbot/production/db-details"
}
