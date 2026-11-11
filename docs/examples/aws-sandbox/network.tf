terraform {
  required_version = ">= 1.5.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 6.0.0"
    }
  }
}

provider "aws" {
  region              = "eu-north-1"
  allowed_account_ids = ["<AWS_ACCOUNT_ID>"]
}

module "network" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "6.0.0"

  name            = "eaaf-sandbox"
  cidr            = "10.42.0.0/16"
  azs             = ["eu-north-1a", "eu-north-1b"]
  private_subnets = ["10.42.10.0/24", "10.42.20.0/24"]

  create_igw                    = false
  enable_nat_gateway            = false
  enable_dns_support            = true
  enable_dns_hostnames          = true
  manage_default_network_acl    = false
  manage_default_route_table    = false
  manage_default_security_group = true

  tags = {
    Project     = "EAAF"
    Environment = "sandbox"
  }
}

output "vpc_id" {
  value = module.network.vpc_id
}

output "private_subnet_ids" {
  value = module.network.private_subnets
}
