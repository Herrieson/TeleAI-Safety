#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo '[1/2] Parsing YAML documents locally'
python - <<'PY'
from pathlib import Path
import sys
try:
    import yaml
except Exception as exc:
    print(f'PyYAML unavailable: {exc}', file=sys.stderr)
    raise SystemExit(2)
base = Path(r'deploy/k8s/rendered-verify-1776061987-2')
for path in sorted(base.glob('*.yaml')):
    with path.open('r', encoding='utf-8') as fh:
        docs = list(yaml.safe_load_all(fh))
    kinds = [doc.get('kind') for doc in docs if isinstance(doc, dict)]
    print(f'{path.name}: ok docs={len(docs)} kinds={kinds}')
PY
if command -v kubectl >/dev/null 2>&1; then
  echo '[2/2] kubectl client-side validation'
  kubectl apply --dry-run=client -f "$DIR/00-namespace.yaml" >/dev/null
  kubectl apply --dry-run=client -f "$DIR/01-configmap.yaml" >/dev/null
  kubectl apply --dry-run=client -f "$DIR/02-secret.yaml" >/dev/null
  kubectl apply --dry-run=client -f "$DIR/03-pvc.yaml" >/dev/null
  kubectl apply --dry-run=client -f "$DIR/04-deployments.yaml" >/dev/null
  kubectl apply --dry-run=client -f "$DIR/05-services.yaml" >/dev/null
  kubectl apply --dry-run=client -f "$DIR/06-ingress.yaml" >/dev/null
  echo 'kubectl dry-run: ok'
else
  echo 'kubectl not found; skipped client-side dry-run validation'
fi
