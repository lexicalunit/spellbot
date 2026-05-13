# Data sources for database secrets created by the db module
data "aws_secretsmanager_secret" "db_password" {
  for_each = local.env_names

  name = "spellbot/${each.key}/db-details"
}
