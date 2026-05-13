# ACM certificate for the environment

resource "aws_acm_certificate" "spellbot" {
  domain_name       = "${var.env_name}.${var.root_domain}"
  validation_method = "DNS"

  tags = {
    Name        = "${var.env_name}.${var.root_domain}"
    Environment = var.env_name
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.spellbot.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = var.route53_zone_id
}

resource "aws_acm_certificate_validation" "spellbot" {
  certificate_arn         = aws_acm_certificate.spellbot.arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation : record.fqdn]
}
