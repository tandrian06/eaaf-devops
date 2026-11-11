module "private_connectivity" {
  source  = "terraform-aws-modules/vpc/aws//modules/vpc-endpoints"
  version = "6.0.0"

  vpc_id     = module.network.vpc_id
  subnet_ids = module.network.private_subnets

  create_security_group      = true
  security_group_name        = "eaaf-sandbox-endpoints"
  security_group_description = "HTTPS from EAAF private subnets to AWS services"
  security_group_rules = {
    private_https = {
      cidr_blocks = module.network.private_subnets_cidr_blocks
    }
  }

  endpoints = merge(
    { for service in ["ecr.api", "ecr.dkr", "logs"] : service => {
      service             = service
      private_dns_enabled = true
    } },
    {
      s3 = {
        service         = "s3"
        service_type    = "Gateway"
        route_table_ids = module.network.private_route_table_ids
        policy = jsonencode({
          Version = "2012-10-17"
          Statement = [{
            Effect    = "Allow"
            Principal = "*"
            Action    = "s3:GetObject"
            Resource  = "arn:aws:s3:::prod-eu-north-1-starport-layer-bucket/*"
          }]
        })
      }
    }
  )

  tags = {
    Project     = "EAAF"
    Environment = "sandbox"
  }
}
