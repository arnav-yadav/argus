output "cluster_endpoint" {
  description = "Kubernetes API endpoint."
  value       = module.eks.cluster_endpoint
}

output "cluster_name" {
  description = "EKS cluster name."
  value       = module.eks.cluster_name
}

output "cluster_version" {
  description = "Kubernetes version running on the control plane."
  value       = module.eks.cluster_version
}

output "configure_kubectl" {
  description = "Command that adds this cluster to your kubeconfig."
  value       = "aws eks update-kubeconfig --region ${var.region} --name ${module.eks.cluster_name} --alias ${module.eks.cluster_name}"
}

output "private_subnets" {
  description = "Private subnet IDs where the worker nodes run."
  value       = module.vpc.private_subnets
}

output "public_subnets" {
  description = "Public subnet IDs (two, one per AZ)."
  value       = module.vpc.public_subnets
}

output "region" {
  description = "Region the cluster runs in."
  value       = var.region
}

output "vpc_id" {
  description = "ID of the VPC."
  value       = module.vpc.vpc_id
}
