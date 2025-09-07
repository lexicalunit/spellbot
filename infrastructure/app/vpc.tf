
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"

  name = "spellbot-vpc"
  cidr = "10.0.0.0/16"

  azs                                    = ["us-east-1a", "us-east-1b", "us-east-1c"]
  private_subnets                        = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets                         = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
  database_subnets                       = ["10.0.21.0/24", "10.0.22.0/24"]
  elasticache_subnets                    = ["10.0.31.0/24"]
  enable_nat_gateway                     = false
  enable_vpn_gateway                     = false
  create_database_subnet_group           = true
  create_database_subnet_route_table     = true
  create_database_internet_gateway_route = true
  create_elasticache_subnet_group        = true
  enable_dns_hostnames                   = true
  enable_dns_support                     = true

}
