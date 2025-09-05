# AWS Secrets Manager secrets for SpellBot

# Production secrets
resource "aws_secretsmanager_secret" "spellbot_prod" {
  name        = "spellbot/production"
  description = "SpellBot production environment secrets"

  tags = {
    Name        = "spellbot-prod-secrets"
    Environment = "production"
  }
}

# Production secret version with initial empty JSON
resource "aws_secretsmanager_secret_version" "spellbot_prod" {
  secret_id     = aws_secretsmanager_secret.spellbot_prod.id
  secret_string = jsonencode({})

  # Ignore changes to secret values (managed manually)
  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Staging secrets
resource "aws_secretsmanager_secret" "spellbot_staging" {
  name        = "spellbot/staging"
  description = "SpellBot staging environment secrets"

  tags = {
    Name        = "spellbot-staging-secrets"
    Environment = "staging"
  }
}

# Staging secret version with initial empty JSON
resource "aws_secretsmanager_secret_version" "spellbot_staging" {
  secret_id     = aws_secretsmanager_secret.spellbot_staging.id
  secret_string = jsonencode({})

  # Ignore changes to secret values (managed manually)
  lifecycle {
    ignore_changes = [secret_string]
  }
}

# SSM Parameters for ECR image tracking

# Staging ECR image tag parameter
# SSM parameters (values ignored by Terraform, managed by deployment script)
resource "aws_ssm_parameter" "spellbot_staging_image_uri" {
  name  = "/spellbot/staging/ecr-image-uri"
  type  = "String"
  value = "latest"

  lifecycle {
    ignore_changes = [value]
  }
}

# Production ECR image tag parameter
# SSM parameters (values ignored by Terraform, managed by deployment script)
resource "aws_ssm_parameter" "spellbot_production_image_uri" {
  name  = "/spellbot/production/ecr-image-uri"
  type  = "String"
  value = "latest"

  lifecycle {
    ignore_changes = [value]
  }
}

# Data sources to read SSM parameters (values managed by deployment script)
# SSM parameters (values ignored by Terraform, managed by deployment script)
data "aws_ssm_parameter" "spellbot_staging_image_uri" {
  depends_on = [aws_ssm_parameter.spellbot_staging_image_uri]
  name       = "/spellbot/staging/ecr-image-uri"
}

data "aws_ssm_parameter" "spellbot_production_image_uri" {
  depends_on = [aws_ssm_parameter.spellbot_production_image_uri]
  name       = "/spellbot/production/ecr-image-uri"
}
