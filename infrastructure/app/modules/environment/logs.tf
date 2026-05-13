# CloudWatch log group for the environment

resource "aws_cloudwatch_log_group" "spellbot" {
  name              = "/ecs/spellbot-${var.env_name}"
  retention_in_days = var.log_retention_days

  tags = {
    Name        = "spellbot-${var.env_name}-logs"
    Environment = var.env_name
  }
}
