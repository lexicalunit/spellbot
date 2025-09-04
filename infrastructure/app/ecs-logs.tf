# CloudWatch log groups
resource "aws_cloudwatch_log_group" "spellbot_prod" {
  name              = "/ecs/spellbot-prod"
  retention_in_days = 30

  tags = {
    Name        = "spellbot-prod-logs"
    Environment = "production"
  }
}

resource "aws_cloudwatch_log_group" "spellbot_staging" {
  name              = "/ecs/spellbot-staging"
  retention_in_days = 7

  tags = {
    Name        = "spellbot-staging-logs"
    Environment = "staging"
  }
}
