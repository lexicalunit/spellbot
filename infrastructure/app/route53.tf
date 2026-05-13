# Main Route53 hosted zone for the root domain
resource "aws_route53_zone" "main" {
  name = var.root_domain

  tags = {
    Name = "${var.root_domain}-zone"
  }
}

locals {
  prod_domain_name  = "prod.${var.root_domain}"
  stage_domain_name = "stage.${var.root_domain}"
}

# Subdomain A records
resource "aws_route53_record" "spellbot" {
  for_each = local.env_names

  zone_id = aws_route53_zone.main.zone_id
  name    = "${each.key}.${var.root_domain}"
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}
