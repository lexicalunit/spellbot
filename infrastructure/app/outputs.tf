# Root-module outputs. Keep this short -- per-environment values are surfaced
# from the environment module; values here are global to the deployment.

output "alb_dns_name" {
  description = "Public DNS name of the shared ALB. Use as the CNAME target for vanity hostnames managed outside this Terraform."
  value       = aws_lb.main.dns_name
}

# DNS-01 validation records for the vanity-domain certificate. These must be
# created in the spellbot.io zone at the registrar before the
# aws_acm_certificate_validation.vanity resource will complete.
output "vanity_acm_validation_records" {
  description = "CNAME records to add at the registrar to validate the vanity-domain ACM certificate."
  value = {
    for dvo in aws_acm_certificate.vanity.domain_validation_options : dvo.domain_name => {
      name  = dvo.resource_record_name
      type  = dvo.resource_record_type
      value = dvo.resource_record_value
    }
  }
}

# Public hostname records. Add these once the cert is validated so the vanity
# URLs resolve to the ALB.
output "vanity_dns_records" {
  description = "CNAME records to add at the registrar so the vanity hostnames resolve to the ALB."
  value = {
    "status.spellbot.io" = {
      type  = "CNAME"
      value = aws_lb.main.dns_name
    }
    "queues.spellbot.io" = {
      type  = "CNAME"
      value = aws_lb.main.dns_name
    }
  }
}
