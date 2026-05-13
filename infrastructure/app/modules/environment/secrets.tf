# Secrets and SSM parameters for the environment

resource "aws_secretsmanager_secret" "spellbot" {
  name        = "spellbot/${var.env_name}"
  description = "SpellBot ${var.env_name} environment secrets"

  tags = {
    Name        = "spellbot-${var.env_name}-secrets"
    Environment = var.env_name
  }
}

resource "aws_secretsmanager_secret_version" "spellbot" {
  secret_id     = aws_secretsmanager_secret.spellbot.id
  secret_string = jsonencode({})

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# SSM Parameter for ECR image tracking (value managed by deployment script)
resource "aws_ssm_parameter" "spellbot_image_uri" {
  name  = "/spellbot/${var.env_name}/ecr-image-uri"
  type  = "String"
  value = "latest"

  lifecycle {
    ignore_changes = [value]
  }
}

# Data source to read SSM parameter
data "aws_ssm_parameter" "spellbot_image_uri" {
  depends_on = [aws_ssm_parameter.spellbot_image_uri]
  name       = "/spellbot/${var.env_name}/ecr-image-uri"
}

# Data source for database secrets created by the db module
data "aws_secretsmanager_secret" "db_password" {
  name = "spellbot/${var.env_name}/db-details"
}
