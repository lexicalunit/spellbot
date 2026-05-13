# CloudWatch log groups

locals {
  log_retention_days = {
    prod  = 5
    stage = 1
  }
}

resource "aws_cloudwatch_log_group" "spellbot" {
  for_each = local.env_names

  name              = "/ecs/spellbot-${each.key}"
  retention_in_days = local.log_retention_days[each.key]

  tags = {
    Name        = "spellbot-${each.key}-logs"
    Environment = each.key
  }
}
