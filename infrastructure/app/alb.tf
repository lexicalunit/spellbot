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

# HTTPS Listener with host-based routing
# Note: Uses prod certificate as default; stage cert added via listener_certificate
# Note: Listener rules are created by environment modules
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = module.prod.certificate_validation_arn

  # Default action (fallback to prod)
  default_action {
    type             = "forward"
    target_group_arn = module.prod.target_group_arn
  }

  tags = {
    Name = "spellbot-https-listener"
  }
}

# Additional certificate for stage domain
resource "aws_lb_listener_certificate" "stage" {
  listener_arn    = aws_lb_listener.https.arn
  certificate_arn = module.stage.certificate_validation_arn
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
