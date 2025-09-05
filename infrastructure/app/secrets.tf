# AWS Secrets Manager secrets for SpellBot

# prod secrets
resource "aws_secretsmanager_secret" "spellbot_prod" {
  name        = "spellbot/prod"
  description = "SpellBot prod environment secrets"

  tags = {
    Name        = "spellbot-prod-secrets"
    Environment = "prod"
  }
}

# prod secret version with initial empty JSON
resource "aws_secretsmanager_secret_version" "spellbot_prod" {
  secret_id     = aws_secretsmanager_secret.spellbot_prod.id
  secret_string = jsonencode({})

  # Ignore changes to secret values (managed manually)
  lifecycle {
    ignore_changes = [secret_string]
  }
}

# stage secrets
resource "aws_secretsmanager_secret" "spellbot_stage" {
  name        = "spellbot/stage"
  description = "SpellBot stage environment secrets"

  tags = {
    Name        = "spellbot-stage-secrets"
    Environment = "stage"
  }
}

# stage secret version with initial empty JSON
resource "aws_secretsmanager_secret_version" "spellbot_stage" {
  secret_id     = aws_secretsmanager_secret.spellbot_stage.id
  secret_string = jsonencode({})

  # Ignore changes to secret values (managed manually)
  lifecycle {
    ignore_changes = [secret_string]
  }
}

# SSM Parameters for ECR image tracking

# stage ECR image tag parameter
# SSM parameters (values ignored by Terraform, managed by deployment script)
resource "aws_ssm_parameter" "spellbot_stage_image_uri" {
  name  = "/spellbot/stage/ecr-image-uri"
  type  = "String"
  value = "latest"

  lifecycle {
    ignore_changes = [value]
  }
}

# prod ECR image tag parameter
# SSM parameters (values ignored by Terraform, managed by deployment script)
resource "aws_ssm_parameter" "spellbot_prod_image_uri" {
  name  = "/spellbot/prod/ecr-image-uri"
  type  = "String"
  value = "latest"

  lifecycle {
    ignore_changes = [value]
  }
}

# Data sources to read SSM parameters (values managed by deployment script)
# SSM parameters (values ignored by Terraform, managed by deployment script)
data "aws_ssm_parameter" "spellbot_stage_image_uri" {
  depends_on = [aws_ssm_parameter.spellbot_stage_image_uri]
  name       = "/spellbot/stage/ecr-image-uri"
}

data "aws_ssm_parameter" "spellbot_prod_image_uri" {
  depends_on = [aws_ssm_parameter.spellbot_prod_image_uri]
  name       = "/spellbot/prod/ecr-image-uri"
}
