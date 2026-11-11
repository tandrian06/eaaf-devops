# AWS Fargate container demo

This module starts one Linux AMD64 Fargate task that serves HTTP on a public IPv4 address. The task uses an existing public subnet with a route to an Internet Gateway.

| Input | Value |
| --- | --- |
| `subnet_id` | Existing public subnet ID |
| `image` | Tagged Linux AMD64 image in Amazon ECR Public |
| `container_port` | The image's HTTP port |
| `client_ipv4_cidr` | Tester's public IPv4 address as a `/32` |

The module returns the cluster and service names. Find the current public IPv4 address in the ECS task networking details. A replacement task can receive a new address. This module uses fixed resource names for one demo per account and region.

The caller configures the AWS provider. Review the plan against the intended account and public subnet before deployment. Keep the Terraform state for cleanup.
