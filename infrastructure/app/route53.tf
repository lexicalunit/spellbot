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

# prod subdomain A record
resource "aws_route53_record" "prod" {
  zone_id = aws_route53_zone.main.zone_id
  name    = local.prod_domain_name
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

# stage subdomain A record
resource "aws_route53_record" "stage" {
  zone_id = aws_route53_zone.main.zone_id
  name    = local.stage_domain_name
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}
