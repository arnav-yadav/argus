module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "21.29.0"

  name               = var.cluster_name
  kubernetes_version = var.kubernetes_version

  # STANDARD means the cluster is upgraded automatically when standard support ends,
  # instead of silently moving to extended support at six times the hourly price.
  upgrade_policy = {
    support_type = "STANDARD"
  }

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # The API server is reachable from the internet only from the listed CIDRs, so kubectl
  # works from the operator's laptop and nowhere else. Nodes reach it privately inside
  # the VPC (endpoint_private_access defaults to true).
  endpoint_public_access       = true
  endpoint_public_access_cidrs = var.api_public_access_cidrs

  # Access entries only, no aws-auth ConfigMap. The identity running Terraform becomes
  # cluster admin through one, and the node group gets its own automatically.
  authentication_mode                      = "API"
  enable_cluster_creator_admin_permissions = true

  # No IAM OIDC provider: nothing here uses IRSA, and pods that need AWS access use EKS
  # Pod Identity (the agent add-on below) instead. This AWS account's organization
  # policy also denies iam:CreateOpenIDConnectProvider, so the first apply stopped here.
  enable_irsa = false

  addons = {
    coredns    = {}
    kube-proxy = {}
    vpc-cni = {
      before_compute = true
    }
    eks-pod-identity-agent = {
      before_compute = true
    }
    # Reports kernel, disk, network and container-runtime faults as node conditions,
    # which the node group's auto repair acts on.
    eks-node-monitoring-agent = {}
  }

  eks_managed_node_groups = {
    default = {
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = [var.node_instance_type]
      capacity_type  = "ON_DEMAND"

      min_size     = var.node_min_size
      max_size     = var.node_max_size
      desired_size = var.node_desired_size

      # This account does not encrypt new EBS volumes by default, so the node disks are
      # encrypted explicitly. The module already requires IMDSv2 with a hop limit of 1,
      # which keeps pods from reaching the node's instance credentials.
      block_device_mappings = {
        root = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size           = 20
            volume_type           = "gp3"
            encrypted             = true
            delete_on_termination = true
          }
        }
      }

      # Replace a node that stays unhealthy, instead of waiting for someone to notice.
      node_repair_config = {
        enabled = true
      }

      labels = {
        workload = "argus"
      }
    }
  }

  # Control-plane audit, API and authenticator logs go to CloudWatch, kept for a day:
  # enough to investigate a demo, cheap, and gone soon after the cluster is.
  enabled_log_types                      = ["api", "audit", "authenticator"]
  create_cloudwatch_log_group            = true
  cloudwatch_log_group_retention_in_days = 1

  # Short-lived demo cluster: no customer-managed KMS key, which would sit in pending
  # deletion for 7+ days after destroy. Kubernetes secrets are still encrypted at rest by
  # EKS's default envelope encryption with an AWS-owned key.
  create_kms_key      = false
  encryption_config   = null
  deletion_protection = false
}
