# Application Load Balancer
resource "aws_lb" "main" {
  name               = "spellbot-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = module.vpc.public_subnets

  enable_deletion_protection = false

  tags = {
    Name = "spellbot-alb"
  }
}

# Target group for prod
resource "aws_lb_target_group" "prod" {
  name                 = "spellbot-prod-tg"
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
    Name        = "spellbot-prod-tg"
    Environment = "prod"
  }
}

# Target group for stage
resource "aws_lb_target_group" "stage" {
  name                 = "spellbot-stage-tg"
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
    Name        = "spellbot-stage-tg"
    Environment = "stage"
  }
}

# HTTPS Listener with host-based routing
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn   = aws_acm_certificate_validation.prod.certificate_arn

  # Default action (fallback to prod)
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.prod.arn
  }

  tags = {
    Name = "spellbot-https-listener"
  }
}

# Additional certificate for stage domain
resource "aws_lb_listener_certificate" "stage" {
  listener_arn    = aws_lb_listener.https.arn
  certificate_arn = aws_acm_certificate_validation.stage.certificate_arn
}

# Listener rule for prod domain
resource "aws_lb_listener_rule" "prod" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.prod.arn
  }

  condition {
    host_header {
      values = ["prod.${var.root_domain}"]
    }
  }

  tags = {
    Name        = "spellbot-prod-rule"
    Environment = "prod"
  }
}

# Listener rule for stage domain
resource "aws_lb_listener_rule" "stage" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 200

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.stage.arn
  }

  condition {
    host_header {
      values = ["stage.${var.root_domain}"]
    }
  }

  tags = {
    Name        = "spellbot-stage-rule"
    Environment = "stage"
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
