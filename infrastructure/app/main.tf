
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  backend "s3" {
    bucket = "spellbot-terraform-state"
    key    = "spellbot-infra"
    region = "us-east-2"
  }
}

provider "aws" {
  region = "us-east-1"
  default_tags {
    tags = {
      Terraform   = "true"
      Environment = "shared"
      App         = "spellbot"
    }
  }
}
