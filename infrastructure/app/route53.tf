# Main Route53 hosted zone for the root domain
resource "aws_route53_zone" "main" {
  name = var.root_domain

  tags = {
    Name = "${var.root_domain}-zone"
  }
}

# Subdomain A records are created by environment modules
