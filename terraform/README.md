# Argus infrastructure on AWS (VPC + EKS)

Provisions a VPC with two public and two private subnets across two availability zones, a
single NAT gateway, and an EKS 1.35 cluster with one managed node group of
`m7i-flex.large` workers.

| File | What it defines |
|---|---|
| `versions.tf` | Terraform and provider version constraints |
| `providers.tf` | AWS provider, region and default tags (`Project=argus`) |
| `vpc.tf` | VPC, 2 public + 2 private subnets, NAT gateway, load-balancer subnet tags |
| `eks.tf` | EKS control plane, logging, add-ons and the managed node group |
| `variables.tf` / `terraform.tfvars.example` | Every tunable, with safe defaults |
| `outputs.tf` | Cluster name, endpoint, VPC and subnet IDs, kubectl command |

## Cost decisions

| Decision | Why |
|---|---|
| Kubernetes **1.35** + `support_type = "STANDARD"` | Versions in extended support bill $0.60/h instead of $0.10/h |
| `m7i-flex.large` nodes | Eligible on the AWS Free plan; `t3.medium` is rejected there |
| One NAT gateway | Half the hourly cost of one per AZ |
| No customer KMS key | It sits in pending deletion for 7+ days after `terraform destroy` |
| Control-plane logs kept for 1 day | Enough to investigate a demo, and they expire soon after the cluster |

Roughly $0.30/hour while running. **Destroy it as soon as the evidence is captured.**

## Security decisions

| Decision | Where |
|---|---|
| Kubernetes API reachable from the internet only from `api_public_access_cidrs` | `eks.tf`, `variables.tf` |
| Worker nodes in private subnets, reaching the API through the private endpoint | `vpc.tf`, `eks.tf` |
| Access entries only (`authentication_mode = "API"`), no `aws-auth` ConfigMap | `eks.tf` |
| Node root volumes encrypted (this account does not encrypt EBS by default) | `eks.tf` |
| IMDSv2 required with a hop limit of 1, so pods cannot borrow the node's credentials | module default, `eks.tf` |
| API, audit and authenticator logs in CloudWatch | `eks.tf` |
| Node monitoring agent plus automatic node repair | `eks.tf` |
| Kubernetes secrets encrypted at rest by EKS's default envelope encryption | AWS default |
| No credentials in this directory; `*.tfvars` and state are gitignored | `.gitignore` |

## Runbook

Credentials come from `aws configure` (an IAM user, never root keys). Nothing secret is
stored in this directory.

```bash
cd terraform
terraform init
terraform fmt -check && terraform validate
echo "api_public_access_cidrs = [\"$(curl -s https://checkip.amazonaws.com)/32\"]" > terraform.tfvars
terraform plan -out argus.tfplan
terraform apply argus.tfplan                     # about 15 minutes
$(terraform output -raw configure_kubectl)
kubectl get nodes -o wide
```

### Tearing down: delete load balancers first

A Kubernetes `LoadBalancer` Service creates an AWS load balancer, with network interfaces
and security groups inside the VPC, that **Terraform does not know about**. If one still
exists, `terraform destroy` hangs on deleting the VPC while the load balancer keeps billing.

```bash
kubectl get svc -A | grep LoadBalancer           # must print nothing
helm -n argus uninstall argus                    # if the app was deployed to EKS
aws elbv2 describe-load-balancers --query 'LoadBalancers[].LoadBalancerName'
aws elb describe-load-balancers --query 'LoadBalancerDescriptions[].LoadBalancerName'
terraform destroy

# Confirm nothing tagged Project=argus is left, and drop the kube context.
aws resourcegroupstaggingapi get-resources --tag-filters Key=Project,Values=argus \
  --query 'ResourceTagMappingList[].ResourceARN'
kubectl config delete-context argus-eks

# EKS can flush a last batch of logs after Terraform deleted the log group, which
# recreates it. Delete it if it came back.
aws logs delete-log-group --log-group-name /aws/eks/argus-eks/cluster 2>/dev/null || true
```
