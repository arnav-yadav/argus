#!/usr/bin/env bash
# One-time cluster bootstrap for Argus on minikube. Safe to re-run.
#   - creates the argus namespace (Pod Security "restricted")
#   - creates the Postgres password Secret outside Git, if it does not exist yet
set -euo pipefail

kubectl apply -f "$(dirname "$0")/../k8s/namespace.yaml"

if kubectl -n argus get secret argus-db >/dev/null 2>&1; then
  echo "secret/argus-db already exists; leaving it alone"
else
  kubectl -n argus create secret generic argus-db \
    --from-literal=password="$(openssl rand -hex 24)"
fi
