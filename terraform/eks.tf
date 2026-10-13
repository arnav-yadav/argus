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

  # Public API endpoint so kubectl works from a laptop; the identity running Terraform
  # becomes cluster admin through an EKS access entry.
  endpoint_public_access                   = true
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
  }

  eks_managed_node_groups = {
    default = {
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = [var.node_instance_type]
      capacity_type  = "ON_DEMAND"

      min_size     = var.node_min_size
      max_size     = var.node_max_size
      desired_size = var.node_desired_size

      labels = {
        workload = "argus"
      }
    }
  }

  # Short-lived demo cluster: skip the resources that outlive `terraform destroy` or
  # bill after it. A customer-managed KMS key sits in pending deletion for 7+ days, and
  # EKS can recreate its CloudWatch log group while the cluster is shutting down.
  # Kubernetes secrets are still encrypted at rest by EKS's default envelope encryption.
  # A production cluster would enable both, plus audit logging.
  create_kms_key              = false
  encryption_config           = null
  create_cloudwatch_log_group = false
  enabled_log_types           = []
  deletion_protection         = false
}
