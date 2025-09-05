# CloudWatch log groups
resource "aws_cloudwatch_log_group" "spellbot_prod" {
  name              = "/ecs/spellbot-prod"
  retention_in_days = 30

  tags = {
    Name        = "spellbot-prod-logs"
    Environment = "prod"
  }
}

resource "aws_cloudwatch_log_group" "spellbot_stage" {
  name              = "/ecs/spellbot-stage"
  retention_in_days = 7

  tags = {
    Name        = "spellbot-stage-logs"
    Environment = "stage"
  }
}
