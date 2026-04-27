#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
kubectl apply -f "$DIR/00-namespace.yaml"
kubectl apply -f "$DIR/01-configmap.yaml"
kubectl apply -f "$DIR/02-secret.yaml"
kubectl apply -f "$DIR/03-pvc.yaml"
kubectl apply -f "$DIR/04-deployments.yaml"
kubectl apply -f "$DIR/05-services.yaml"
kubectl apply -f "$DIR/06-ingress.yaml"
