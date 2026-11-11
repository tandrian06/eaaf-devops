variable "subnet_id" {
  description = "An existing public subnet with an IPv4 default route to an internet gateway."
  type        = string
}

variable "image" {
  description = "A tagged, anonymously pullable Linux AMD64 image in Amazon ECR Public."
  type        = string

  validation {
    condition     = can(regex("^public\\.ecr\\.aws/[a-z0-9][a-z0-9._/-]*:[A-Za-z0-9_][A-Za-z0-9_.-]*$", var.image))
    error_message = "Provide a tagged image in Amazon ECR Public."
  }
}

variable "container_port" {
  description = "The port on which the demo container serves HTTP."
  type        = number

  validation {
    condition     = var.container_port >= 1 && var.container_port <= 65535 && floor(var.container_port) == var.container_port
    error_message = "Provide an integer port between 1 and 65535."
  }
}

variable "client_ipv4_cidr" {
  description = "The tester's public IPv4 address as a /32 CIDR."
  type        = string

  validation {
    condition     = can(cidrnetmask(var.client_ipv4_cidr)) && endswith(var.client_ipv4_cidr, "/32")
    error_message = "Provide a valid IPv4 /32 CIDR."
  }
}
