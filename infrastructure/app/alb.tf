# Application Load Balancer
resource "aws_lb" "main" {
  name               = "spellbot-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = module.vpc.public_subnets

  enable_deletion_protection = true

  tags = {
    Name = "spellbot-alb"
  }
}

# Target groups
resource "aws_lb_target_group" "spellbot" {
  for_each = local.env_names

  name                 = "spellbot-${each.key}-tg"
  port                 = 80
  protocol             = "HTTP"
  vpc_id               = module.vpc.vpc_id
  target_type          = "ip"
  deregistration_delay = 5

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 2
  }

  tags = {
    Name        = "spellbot-${each.key}-tg"
    Environment = each.key
  }
}

# HTTPS Listener with host-based routing
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate_validation.spellbot["prod"].certificate_arn

  # Default action (fallback to prod)
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.spellbot["prod"].arn
  }

  tags = {
    Name = "spellbot-https-listener"
  }
}

# Additional certificate for stage domain
resource "aws_lb_listener_certificate" "stage" {
  listener_arn    = aws_lb_listener.https.arn
  certificate_arn = aws_acm_certificate_validation.spellbot["stage"].certificate_arn
}

locals {
  listener_rule_priority = {
    prod  = 100
    stage = 200
  }
}

# Listener rules for host-based routing
resource "aws_lb_listener_rule" "spellbot" {
  for_each = local.env_names

  listener_arn = aws_lb_listener.https.arn
  priority     = local.listener_rule_priority[each.key]

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.spellbot[each.key].arn
  }

  condition {
    host_header {
      values = ["${each.key}.${var.root_domain}"]
    }
  }

  tags = {
    Name        = "spellbot-${each.key}-rule"
    Environment = each.key
  }
}

# HTTP Listener (redirect to HTTPS)
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }

  tags = {
    Name = "spellbot-http-listener"
  }
}
