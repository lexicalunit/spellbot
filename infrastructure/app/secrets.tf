# AWS Secrets Manager secrets for SpellBot

locals {
  env_names = toset(["prod", "stage"])
}

resource "aws_secretsmanager_secret" "spellbot" {
  for_each = local.env_names

  name        = "spellbot/${each.key}"
  description = "SpellBot ${each.key} environment secrets"

  tags = {
    Name        = "spellbot-${each.key}-secrets"
    Environment = each.key
  }
}

resource "aws_secretsmanager_secret_version" "spellbot" {
  for_each = local.env_names

  secret_id     = aws_secretsmanager_secret.spellbot[each.key].id
  secret_string = jsonencode({})

  # Ignore changes to secret values (managed manually)
  lifecycle {
    ignore_changes = [secret_string]
  }
}

# SSM Parameters for ECR image tracking (values managed by deployment script)
resource "aws_ssm_parameter" "spellbot_image_uri" {
  for_each = local.env_names

  name  = "/spellbot/${each.key}/ecr-image-uri"
  type  = "String"
  value = "latest"

  lifecycle {
    ignore_changes = [value]
  }
}

# Data sources to read SSM parameters (values managed by deployment script)
data "aws_ssm_parameter" "spellbot_image_uri" {
  for_each = local.env_names

  depends_on = [aws_ssm_parameter.spellbot_image_uri]
  name       = "/spellbot/${each.key}/ecr-image-uri"
}
