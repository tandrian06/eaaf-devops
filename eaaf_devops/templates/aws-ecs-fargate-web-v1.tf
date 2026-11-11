terraform {
  required_version = ">= 1.5.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 6.0.0"
    }
  }
}

locals {
  # EAAF_MANIFEST
}

provider "aws" {
  region = local.region
}

variable "name" {
  description = "Name of the workload and load balancer."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$", var.name)) && !startswith(var.name, "internal-")
    error_message = "Use a lowercase ALB name of at most 32 characters without the internal- prefix."
  }
}

variable "alb_subnet_ids" {
  description = "Existing ALB subnets in distinct availability zones. Use public subnets for a public ALB."
  type        = set(string)

  validation {
    condition     = length(var.alb_subnet_ids) >= 2
    error_message = "Provide at least two distinct ALB subnets."
  }
}

variable "client_ipv4_cidrs" {
  description = "IPv4 networks authorized to reach the HTTPS listener."
  type        = set(string)

  validation {
    condition     = length(var.client_ipv4_cidrs) > 0 && alltrue([for cidr in var.client_ipv4_cidrs : can(cidrnetmask(cidr))])
    error_message = "Provide at least one valid IPv4 CIDR."
  }
}

data "aws_subnet" "task" {
  for_each = toset(local.task_subnet_ids)
  id       = each.key
}

module "alb" {
  source  = "terraform-aws-modules/alb/aws"
  version = "9.17.0"

  name     = var.name
  internal = local.internal
  vpc_id   = local.vpc_id
  subnets  = sort(tolist(var.alb_subnet_ids))

  security_group_ingress_rules = {
    for cidr in var.client_ipv4_cidrs : cidr => {
      ip_protocol = "tcp"
      from_port   = 443
      to_port     = 443
      cidr_ipv4   = cidr
    }
  }

  security_group_egress_rules = {
    for id, subnet in data.aws_subnet.task : id => {
      ip_protocol = "tcp"
      from_port   = local.container_port
      to_port     = local.container_port
      cidr_ipv4   = subnet.cidr_block
    }
  }

  listeners = {
    https = {
      port            = 443
      protocol        = "HTTPS"
      certificate_arn = local.certificate_arn
      ssl_policy      = "ELBSecurityPolicy-TLS13-1-2-2021-06"
      forward = {
        target_group_key = "app"
      }
    }
  }

  target_groups = {
    app = {
      backend_protocol  = "HTTP"
      backend_port      = local.container_port
      target_type       = "ip"
      create_attachment = false
      health_check = {
        enabled = true
        path    = "/"
      }
    }
  }
}

module "cluster" {
  source  = "terraform-aws-modules/ecs/aws//modules/cluster"
  version = "6.0.0"

  name = var.name

  default_capacity_provider_strategy = {
    FARGATE = { weight = 1 }
  }
}

module "service" {
  source  = "terraform-aws-modules/ecs/aws//modules/service"
  version = "6.0.0"

  name             = var.name
  cluster_arn      = module.cluster.arn
  launch_type      = "FARGATE"
  cpu              = 256
  memory           = 512
  desired_count    = 2
  subnet_ids       = local.task_subnet_ids
  assign_public_ip = false

  create_task_exec_iam_role = true
  create_task_exec_policy   = true
  create_tasks_iam_role     = false

  container_definitions = {
    app = {
      image = local.image
      portMappings = [{
        containerPort = local.container_port
        protocol      = "tcp"
      }]
    }
  }

  load_balancer = {
    app = {
      target_group_arn = module.alb.target_groups["app"].arn
      container_name   = "app"
      container_port   = local.container_port
    }
  }

  security_group_ingress_rules = {
    alb = {
      ip_protocol                  = "tcp"
      from_port                    = local.container_port
      to_port                      = local.container_port
      referenced_security_group_id = module.alb.security_group_id
    }
  }

  security_group_egress_rules = {
    https = {
      ip_protocol = "tcp"
      from_port   = 443
      to_port     = 443
      cidr_ipv4   = "0.0.0.0/0"
    }
  }

  depends_on = [module.alb]
}

output "alb_dns_name" {
  value = module.alb.dns_name
}

output "application_domain" {
  value = local.domain_name
}

output "expected_outbound_access" {
  value = local.outbound_access
}
