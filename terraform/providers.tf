provider "aws" {
  region = var.region

  # Every resource is tagged, so a leftover can be found by tag after `terraform destroy`:
  #   aws resourcegroupstaggingapi get-resources --tag-filters Key=Project,Values=argus
  default_tags {
    tags = {
      Project     = "argus"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
