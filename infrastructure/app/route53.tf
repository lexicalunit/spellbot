# Main Route53 hosted zone for the root domain
resource "aws_route53_zone" "main" {
  name = var.root_domain

  tags = {
    Name = "${var.root_domain}-zone"
  }
}

# Production subdomain A record
resource "aws_route53_record" "prod" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "prod.${var.root_domain}"
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

# Staging subdomain A record
resource "aws_route53_record" "staging" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "staging.${var.root_domain}"
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}
