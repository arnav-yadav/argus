variable "cluster_name" {
  description = "Name of the EKS cluster and prefix for the VPC."
  type        = string
  default     = "argus-eks"
}

variable "environment" {
  description = "Environment name, used in tags."
  type        = string
  default     = "demo"
}

variable "kubernetes_version" {
  description = "EKS Kubernetes version. Must be in STANDARD support: versions in extended support cost 6x as much per hour."
  type        = string
  default     = "1.35"

  validation {
    condition     = can(regex("^1\\.[0-9]+$", var.kubernetes_version))
    error_message = "kubernetes_version must be a minor version such as \"1.35\"."
  }
}

variable "node_desired_size" {
  description = "Number of worker nodes to start with."
  type        = number
  default     = 2

  validation {
    condition     = var.node_min_size <= var.node_desired_size && var.node_desired_size <= var.node_max_size
    error_message = "node_desired_size must lie between node_min_size and node_max_size."
  }
}

variable "node_instance_type" {
  description = "Worker node instance type. m7i-flex.large (2 vCPU, 8 GiB) is eligible on the AWS Free plan; t3.medium is not."
  type        = string
  default     = "m7i-flex.large"
}

variable "node_max_size" {
  description = "Maximum number of worker nodes."
  type        = number
  default     = 3
}

variable "node_min_size" {
  description = "Minimum number of worker nodes."
  type        = number
  default     = 1

  validation {
    condition     = var.node_min_size >= 1
    error_message = "node_min_size must be at least 1, or nothing can be scheduled."
  }
}

variable "region" {
  description = "AWS region. This account's policy only permits ap-southeast-2 (Sydney)."
  type        = string
  default     = "ap-southeast-2"

  validation {
    condition     = can(regex("^[a-z]{2}(-[a-z]+)+-[0-9]$", var.region))
    error_message = "region must be an AWS region code such as \"ap-southeast-2\"."
  }
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.42.0.0/16"

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "vpc_cidr must be a valid IPv4 CIDR block such as \"10.42.0.0/16\"."
  }
}
