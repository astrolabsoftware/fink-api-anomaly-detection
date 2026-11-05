#!/usr/bin/env bash
set -euo pipefail

if [[ $# -gt 1 ]]; then
    echo "Usage: $0 [cert-manager-version]" >&2
    exit 2
fi

if ! command -v kubectl >/dev/null 2>&1; then
    echo "This script requires kubectl." >&2
    exit 1
fi

version=${1:-v1.18.2}

kubectl apply -f "https://github.com/cert-manager/cert-manager/releases/download/${version}/cert-manager.yaml"
kubectl rollout status deployment/cert-manager -n cert-manager --timeout=180s
kubectl rollout status deployment/cert-manager-cainjector -n cert-manager --timeout=180s
kubectl rollout status deployment/cert-manager-webhook -n cert-manager --timeout=180s
kubectl wait --for=condition=Established --timeout=120s crd/clusterissuers.cert-manager.io
