#!/usr/bin/env bash
# One-time cluster bootstrap for Argus on minikube. Safe to re-run.
#   - creates the argus and argus-staging namespaces (Pod Security "restricted")
#   - creates each environment's Postgres password Secret outside Git, if missing
set -euo pipefail

kubectl apply -f "$(dirname "$0")/../k8s/namespace.yaml"

for ns in argus argus-staging; do
  if kubectl -n "$ns" get secret argus-db >/dev/null 2>&1; then
    echo "$ns: secret/argus-db already exists; leaving it alone"
  else
    kubectl -n "$ns" create secret generic argus-db \
      --from-literal=password="$(openssl rand -hex 24)"
  fi
done
