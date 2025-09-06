# ACM certificate for prod subdomain
resource "aws_acm_certificate" "prod" {
  domain_name       = "prod.${var.root_domain}"
  validation_method = "DNS"

  tags = {
    Name        = "prod.${var.root_domain}"
    Environment = "prod"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# ACM certificate for stage subdomain
resource "aws_acm_certificate" "stage" {
  domain_name       = "stage.${var.root_domain}"
  validation_method = "DNS"

  tags = {
    Name        = "stage.${var.root_domain}"
    Environment = "stage"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# DNS validation records for prod certificate
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

# DNS validation records for stage certificate
resource "aws_route53_record" "stage_cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.stage.domain_validation_options : dvo.domain_name => {
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

# Certificate validation for prod
resource "aws_acm_certificate_validation" "prod" {
  certificate_arn         = aws_acm_certificate.prod.arn
  validation_record_fqdns = [for record in aws_route53_record.prod_cert_validation : record.fqdn]
}

# Certificate validation for stage
resource "aws_acm_certificate_validation" "stage" {
  certificate_arn         = aws_acm_certificate.stage.arn
  validation_record_fqdns = [for record in aws_route53_record.stage_cert_validation : record.fqdn]
}
