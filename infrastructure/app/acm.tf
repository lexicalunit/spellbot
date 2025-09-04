# ACM certificate for production subdomain
resource "aws_acm_certificate" "prod" {
  domain_name       = "prod.${var.root_domain}"
  validation_method = "DNS"

  tags = {
    Name        = "prod.${var.root_domain}"
    Environment = "production"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# ACM certificate for staging subdomain
resource "aws_acm_certificate" "staging" {
  domain_name       = "staging.${var.root_domain}"
  validation_method = "DNS"

  tags = {
    Name        = "staging.${var.root_domain}"
    Environment = "staging"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# DNS validation records for production certificate
resource "aws_route53_record" "prod_cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.prod.domain_validation_options : dvo.domain_name => {
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
  zone_id         = aws_route53_zone.main.zone_id
}

# DNS validation records for staging certificate
resource "aws_route53_record" "staging_cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.staging.domain_validation_options : dvo.domain_name => {
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
  zone_id         = aws_route53_zone.main.zone_id
}

# Certificate validation for production
resource "aws_acm_certificate_validation" "prod" {
  certificate_arn         = aws_acm_certificate.prod.arn
  validation_record_fqdns = [for record in aws_route53_record.prod_cert_validation : record.fqdn]
}

# Certificate validation for staging
resource "aws_acm_certificate_validation" "staging" {
  certificate_arn         = aws_acm_certificate.staging.arn
  validation_record_fqdns = [for record in aws_route53_record.staging_cert_validation : record.fqdn]
}

