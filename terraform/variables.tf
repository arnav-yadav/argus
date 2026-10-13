variable "region" {
  description = "AWS region. This account's policy only permits ap-southeast-2 (Sydney)."
  type        = string
  default     = "ap-southeast-2"
}

variable "environment" {
  description = "Environment name, used in tags."
  type        = string
  default     = "demo"
}

variable "cluster_name" {
  description = "Name of the EKS cluster and prefix for the VPC."
  type        = string
  default     = "argus-eks"
}

variable "kubernetes_version" {
  description = "EKS Kubernetes version. Must be in STANDARD support: versions in extended support cost 6x as much per hour."
  type        = string
  default     = "1.35"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.42.0.0/16"
}

variable "node_instance_type" {
  description = "Worker node instance type. m7i-flex.large (2 vCPU, 8 GiB) is eligible on the AWS Free plan; t3.medium is not."
  type        = string
  default     = "m7i-flex.large"
}

variable "node_desired_size" {
  description = "Number of worker nodes to start with."
  type        = number
  default     = 2
}

variable "node_min_size" {
  description = "Minimum number of worker nodes."
  type        = number
  default     = 1
}

variable "node_max_size" {
  description = "Maximum number of worker nodes."
  type        = number
  default     = 3
}
