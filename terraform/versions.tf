terraform {
  required_version = ">= 1.11.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.59" # the EKS module v21.29 needs >= 6.59
    }
  }
}
