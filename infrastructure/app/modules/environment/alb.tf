# ALB target group and listener rule for the environment

resource "aws_lb_target_group" "spellbot" {
  name                 = "spellbot-${var.env_name}-tg"
  port                 = 80
  protocol             = "HTTP"
  vpc_id               = var.vpc_id
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
    Name        = "spellbot-${var.env_name}-tg"
    Environment = var.env_name
  }
}

resource "aws_lb_listener_rule" "spellbot" {
  listener_arn = var.alb_listener_arn
  priority     = var.listener_rule_priority

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.spellbot.arn
  }

  condition {
    host_header {
      values = ["${var.env_name}.${var.root_domain}"]
    }
  }

  tags = {
    Name        = "spellbot-${var.env_name}-rule"
    Environment = var.env_name
  }
}
