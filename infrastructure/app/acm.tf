# ACM certificates for subdomains
resource "aws_acm_certificate" "spellbot" {
  for_each = local.env_names

  domain_name       = "${each.key}.${var.root_domain}"
  validation_method = "DNS"

  tags = {
    Name        = "${each.key}.${var.root_domain}"
    Environment = each.key
  }

  lifecycle {
    create_before_destroy = true
  }
}

# DNS validation records for certificates
resource "aws_route53_record" "cert_validation" {
  for_each = {
    for item in flatten([
      for env in local.env_names : [
        for dvo in aws_acm_certificate.spellbot[env].domain_validation_options : {
          key    = "${env}-${dvo.domain_name}"
          env    = env
          name   = dvo.resource_record_name
          record = dvo.resource_record_value
          type   = dvo.resource_record_type
        }
      ]
    ]) : item.key => item
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = aws_route53_zone.main.zone_id
}

# Certificate validations
resource "aws_acm_certificate_validation" "spellbot" {
  for_each = local.env_names

  certificate_arn = aws_acm_certificate.spellbot[each.key].arn
  validation_record_fqdns = [
    for key, record in aws_route53_record.cert_validation :
    record.fqdn if startswith(key, "${each.key}-")
  ]
}
