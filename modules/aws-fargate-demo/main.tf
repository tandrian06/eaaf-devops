terraform {
  required_version = ">= 1.5.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.0.0, < 7.0.0"
    }
  }
}

data "aws_subnet" "demo" {
  id = var.subnet_id
}

resource "aws_ecs_cluster" "demo" {
  name = "eaaf-container-demo"
}

resource "aws_security_group" "demo" {
  name_prefix = "eaaf-container-demo-"
  description = "EAAF demo container access"
  vpc_id      = data.aws_subnet.demo.vpc_id

  ingress {
    description = "HTTP from the tester"
    from_port   = var.container_port
    to_port     = var.container_port
    protocol    = "tcp"
    cidr_blocks = [var.client_ipv4_cidr]
  }

  egress {
    description = "HTTPS for the public image pull"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_ecs_task_definition" "demo" {
  family                   = "eaaf-container-demo"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512

  container_definitions = jsonencode([{
    name      = "demo"
    image     = var.image
    essential = true
    portMappings = [{
      containerPort = var.container_port
      protocol      = "tcp"
    }]
  }])
}

resource "aws_ecs_service" "demo" {
  name            = "eaaf-container-demo"
  cluster         = aws_ecs_cluster.demo.id
  task_definition = aws_ecs_task_definition.demo.arn
  launch_type     = "FARGATE"
  desired_count   = 1

  network_configuration {
    subnets          = [var.subnet_id]
    security_groups  = [aws_security_group.demo.id]
    assign_public_ip = true
  }
}

output "cluster_name" {
  value = aws_ecs_cluster.demo.name
}

output "service_name" {
  value = aws_ecs_service.demo.name
}
