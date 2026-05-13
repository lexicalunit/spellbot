# Route53 A record for the environment

resource "aws_route53_record" "spellbot" {
  zone_id = var.route53_zone_id
  name    = "${var.env_name}.${var.root_domain}"
  type    = "A"

  alias {
    name                   = var.alb_dns_name
    zone_id                = var.alb_zone_id
    evaluate_target_health = true
  }
}
