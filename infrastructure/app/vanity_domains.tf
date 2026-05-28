# Vanity hostnames pointed at the prod environment.
#
# These hostnames live in the `spellbot.io` apex zone, which is NOT managed by
# this Terraform (the apex is on an external registrar). The cert below is
# therefore created with DNS validation but without the auto-generated Route53
# validation records that the per-environment module uses; the validation
# CNAMEs and the public hostname records must be added by hand at the
# registrar, using the values surfaced in outputs.tf.
#
# Apply workflow:
#
#   1. terraform apply -target=aws_acm_certificate.vanity
#   2. terraform output vanity_acm_validation_records
#      -> add each CNAME to the spellbot.io zone at the registrar.
#   3. terraform apply
#      (aws_acm_certificate_validation polls until the cert is ISSUED,
#       then attaches it to the listener and creates the rules).
#   4. terraform output vanity_dns_records
#      -> add `status.spellbot.io` and `queues.spellbot.io` CNAMEs pointing
#         at the ALB hostname.
#
# After step 4 the bare URLs 301 to /status and /queues respectively and
# all other paths on those hosts forward to the prod target group.

locals {
  vanity_status_host = "status.spellbot.io"
  vanity_queues_host = "queues.spellbot.io"
}

resource "aws_acm_certificate" "vanity" {
  domain_name               = local.vanity_status_host
  subject_alternative_names = [local.vanity_queues_host]
  validation_method         = "DNS"

  tags = {
    Name = "spellbot-vanity-cert"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Polls ACM until the cert reaches ISSUED state. With no
# `validation_record_fqdns` set, this waits on the cert itself rather than on
# any Route53 records (which TF cannot create in the apex zone). Allow up to
# 60 minutes so DNS records added by hand at the registrar have time to
# propagate.
resource "aws_acm_certificate_validation" "vanity" {
  certificate_arn = aws_acm_certificate.vanity.arn

  timeouts {
    create = "60m"
  }
}

resource "aws_lb_listener_certificate" "vanity" {
  listener_arn    = aws_lb_listener.https.arn
  certificate_arn = aws_acm_certificate_validation.vanity.certificate_arn
}

# Redirect the bare URL to the path that actually renders the page. `#{host}`
# preserves the original hostname so the redirect stays on the vanity domain.
resource "aws_lb_listener_rule" "vanity_status_root_redirect" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 50

  action {
    type = "redirect"
    redirect {
      protocol    = "HTTPS"
      port        = "443"
      host        = "#{host}"
      path        = "/status"
      query       = "#{query}"
      status_code = "HTTP_301"
    }
  }

  condition {
    host_header {
      values = [local.vanity_status_host]
    }
  }
  condition {
    path_pattern {
      values = ["/"]
    }
  }

  tags = {
    Name = "spellbot-vanity-status-root"
  }
}

resource "aws_lb_listener_rule" "vanity_status_forward" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 51

  action {
    type             = "forward"
    target_group_arn = module.prod.target_group_arn
  }

  condition {
    host_header {
      values = [local.vanity_status_host]
    }
  }

  tags = {
    Name = "spellbot-vanity-status-forward"
  }
}

resource "aws_lb_listener_rule" "vanity_queues_root_redirect" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 52

  action {
    type = "redirect"
    redirect {
      protocol    = "HTTPS"
      port        = "443"
      host        = "#{host}"
      path        = "/queues"
      query       = "#{query}"
      status_code = "HTTP_301"
    }
  }

  condition {
    host_header {
      values = [local.vanity_queues_host]
    }
  }
  condition {
    path_pattern {
      values = ["/"]
    }
  }

  tags = {
    Name = "spellbot-vanity-queues-root"
  }
}

resource "aws_lb_listener_rule" "vanity_queues_forward" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 53

  action {
    type             = "forward"
    target_group_arn = module.prod.target_group_arn
  }

  condition {
    host_header {
      values = [local.vanity_queues_host]
    }
  }

  tags = {
    Name = "spellbot-vanity-queues-forward"
  }
}
