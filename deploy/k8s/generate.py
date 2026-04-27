#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex


def parse_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        data[key] = value
    return data


def yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def pvc_doc(name: str, namespace: str, size: str, storage_class: str) -> str:
    storage_class_block = f"  storageClassName: {yaml_quote(storage_class)}\n" if storage_class else ""
    return f"""apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {name}
  namespace: {namespace}
spec:
  accessModes:
    - ReadWriteOnce
{storage_class_block}  resources:
    requests:
      storage: {yaml_quote(size)}
"""


def env_from_map(name: str) -> str:
    return (
        "\n"
        "            - configMapRef:\n"
        f"                name: {name}\n"
        "            - secretRef:\n"
        f"                name: {name}-secret"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate beginner-friendly Kubernetes manifests for TeleAI-Safety.")
    parser.add_argument("--env-file", default="deploy/k8s/deploy.env", help="Path to the deployment env file.")
    parser.add_argument("--output-dir", default="deploy/k8s/rendered", help="Directory to write rendered manifests into.")
    args = parser.parse_args()

    env_path = Path(args.env_file)
    if not env_path.exists():
        raise SystemExit(f"env file not found: {env_path} (copy deploy/k8s/deploy.env.example first)")

    file_env = parse_env_file(env_path)

    def get(name: str, default: str = "") -> str:
        return os.getenv(name, file_env.get(name, default))

    namespace = get("NAMESPACE")
    domain = get("DOMAIN")
    web_image = get("WEB_IMAGE")
    python_services_image = get("PYTHON_SERVICES_IMAGE")
    bff_image = get("BFF_IMAGE", python_services_image)
    orch_image = get("ORCH_IMAGE", python_services_image)

    missing = [
        key
        for key, value in {
            "NAMESPACE": namespace,
            "DOMAIN": domain,
            "WEB_IMAGE": web_image,
            "PYTHON_SERVICES_IMAGE or BFF_IMAGE/ORCH_IMAGE": python_services_image or (bff_image and orch_image),
        }.items()
        if not value
    ]
    if missing:
        raise SystemExit("missing required values in env file: " + ", ".join(missing))

    app_name = get("APP_NAME", "teleai-safety")
    ingress_class = get("INGRESS_CLASS", "nginx")
    enable_tls = truthy(get("ENABLE_TLS", "true"))
    tls_secret_name = get("TLS_SECRET_NAME", f"{app_name}-tls")
    web_replicas = get("WEB_REPLICAS", "1")
    bff_replicas = get("BFF_REPLICAS", "1")
    orch_replicas = get("ORCH_REPLICAS", "1")
    storage_class = get("STORAGE_CLASS", "")
    data_storage_size = get("DATA_STORAGE_SIZE", "100Gi")
    benchmark_storage_size = get("BENCHMARK_STORAGE_SIZE", "100Gi")
    evaluate_storage_size = get("EVALUATE_STORAGE_SIZE", "100Gi")

    config_values = {
        "HOST": "0.0.0.0",
        "PORT": "3000",
        "NEXT_PUBLIC_BFF_BASE_URL": get("NEXT_PUBLIC_BFF_BASE_URL", ""),
        "BFF_HTTP_TIMEOUT": get("BFF_HTTP_TIMEOUT", "20"),
        "BFF_CORS_ALLOW_ORIGINS": get("BFF_CORS_ALLOW_ORIGINS", f"https://{domain}"),
        "ORCHESTRATOR_BASE_URL": get("ORCHESTRATOR_BASE_URL", "http://telert-orchestrator:9001"),
        "TELEAI_TZ": get("TELEAI_TZ", "Asia/Shanghai"),
        "TELEAI_INTERNAL_LLM_BASE_URL": get("TELEAI_INTERNAL_LLM_BASE_URL", ""),
        "TELEAI_INTERNAL_LLM_MODEL": get("TELEAI_INTERNAL_LLM_MODEL", "gpt-4o-mini"),
        "TELEAI_USE_INTERNAL_LLM_FOR_ATTACK": get("TELEAI_USE_INTERNAL_LLM_FOR_ATTACK", "true"),
        "TELEAI_USE_INTERNAL_LLM_FOR_EVALUATE": get("TELEAI_USE_INTERNAL_LLM_FOR_EVALUATE", "true"),
        "TELEAI_STRICT_CRED_ISOLATION": get("TELEAI_STRICT_CRED_ISOLATION", "true"),
        "BFF_MANAGED_MODE_MAX_ACTIVE_RUNS_GLOBAL": get("BFF_MANAGED_MODE_MAX_ACTIVE_RUNS_GLOBAL", "6"),
        "BFF_MANAGED_MODE_MAX_ACTIVE_RUNS_PER_IP": get("BFF_MANAGED_MODE_MAX_ACTIVE_RUNS_PER_IP", "2"),
        "BFF_MANAGED_MODE_MIN_INTERVAL_SECONDS": get("BFF_MANAGED_MODE_MIN_INTERVAL_SECONDS", "300"),
        "BFF_MANAGED_MODE_ACCESS_CONTROL_ENABLED": get("BFF_MANAGED_MODE_ACCESS_CONTROL_ENABLED", "false"),
        "BFF_MANAGED_MODE_IP_WHITELIST": get("BFF_MANAGED_MODE_IP_WHITELIST", "127.0.0.1,::1"),
    }

    secret_values = {
        "TELEAI_INTERNAL_LLM_API_KEY": get("TELEAI_INTERNAL_LLM_API_KEY", ""),
        "BFF_MANAGED_MODE_INVITE_CODES": get("BFF_MANAGED_MODE_INVITE_CODES", ""),
        "TELEAI_MANAGED_TARGET_MODELS": get("TELEAI_MANAGED_TARGET_MODELS", ""),
    }

    configmap_body = "\n".join(f"  {key}: {yaml_quote(value)}" for key, value in config_values.items())
    secret_body = "\n".join(f"  {key}: {yaml_quote(value)}" for key, value in secret_values.items())

    tls_block = (
        f"  tls:\n    - hosts:\n        - {domain}\n      secretName: {tls_secret_name}\n"
        if enable_tls
        else ""
    )

    namespace_doc = f"""apiVersion: v1
kind: Namespace
metadata:
  name: {namespace}
"""

    configmap_doc = f"""apiVersion: v1
kind: ConfigMap
metadata:
  name: {app_name}-config
  namespace: {namespace}
data:
{configmap_body}
"""

    secret_doc = f"""apiVersion: v1
kind: Secret
metadata:
  name: {app_name}-config-secret
  namespace: {namespace}
type: Opaque
stringData:
{secret_body}
"""

    pvc_docs = "---\n".join(
        [
            pvc_doc(f"{app_name}-data-pvc", namespace, data_storage_size, storage_class),
            pvc_doc(f"{app_name}-benchmark-pvc", namespace, benchmark_storage_size, storage_class),
            pvc_doc(f"{app_name}-evaluate-pvc", namespace, evaluate_storage_size, storage_class),
        ]
    )

    deployments_doc = f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: telert-web
  namespace: {namespace}
  labels:
    app.kubernetes.io/name: {app_name}
    app.kubernetes.io/component: web
spec:
  replicas: {web_replicas}
  selector:
    matchLabels:
      app.kubernetes.io/name: {app_name}
      app.kubernetes.io/component: web
  template:
    metadata:
      labels:
        app.kubernetes.io/name: {app_name}
        app.kubernetes.io/component: web
    spec:
      containers:
        - name: web
          image: {web_image}
          imagePullPolicy: IfNotPresent
          env:
            - name: HOST
              valueFrom:
                configMapKeyRef:
                  name: {app_name}-config
                  key: HOST
            - name: PORT
              valueFrom:
                configMapKeyRef:
                  name: {app_name}-config
                  key: PORT
            - name: NEXT_PUBLIC_BFF_BASE_URL
              valueFrom:
                configMapKeyRef:
                  name: {app_name}-config
                  key: NEXT_PUBLIC_BFF_BASE_URL
          ports:
            - name: http
              containerPort: 3000
          readinessProbe:
            httpGet:
              path: /runs
              port: http
            initialDelaySeconds: 10
            periodSeconds: 10
          livenessProbe:
            tcpSocket:
              port: http
            initialDelaySeconds: 30
            periodSeconds: 20
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: telert-bff
  namespace: {namespace}
  labels:
    app.kubernetes.io/name: {app_name}
    app.kubernetes.io/component: bff
spec:
  replicas: {bff_replicas}
  selector:
    matchLabels:
      app.kubernetes.io/name: {app_name}
      app.kubernetes.io/component: bff
  template:
    metadata:
      labels:
        app.kubernetes.io/name: {app_name}
        app.kubernetes.io/component: bff
    spec:
      containers:
        - name: bff
          image: {bff_image}
          imagePullPolicy: IfNotPresent
          command: ["uv", "run", "python", "-m", "uvicorn", "services.bff.app.main:app", "--host", "0.0.0.0", "--port", "9000"]
          envFrom:{env_from_map(f'{app_name}-config')}
          ports:
            - name: http
              containerPort: 9000
          readinessProbe:
            httpGet:
              path: /api/health
              port: http
            initialDelaySeconds: 10
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 30
            periodSeconds: 20
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: telert-orchestrator
  namespace: {namespace}
  labels:
    app.kubernetes.io/name: {app_name}
    app.kubernetes.io/component: orchestrator
spec:
  replicas: {orch_replicas}
  selector:
    matchLabels:
      app.kubernetes.io/name: {app_name}
      app.kubernetes.io/component: orchestrator
  template:
    metadata:
      labels:
        app.kubernetes.io/name: {app_name}
        app.kubernetes.io/component: orchestrator
    spec:
      containers:
        - name: orchestrator
          image: {orch_image}
          imagePullPolicy: IfNotPresent
          command: ["uv", "run", "python", "-m", "uvicorn", "services.orchestrator.app.main:app", "--host", "0.0.0.0", "--port", "9001"]
          envFrom:{env_from_map(f'{app_name}-config')}
          ports:
            - name: http
              containerPort: 9001
          volumeMounts:
            - name: teleai-data
              mountPath: /app/data
            - name: teleai-benchmark
              mountPath: /app/benchmark/result
            - name: teleai-evaluate
              mountPath: /app/evaluate/evaluation_report
          readinessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 10
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 30
            periodSeconds: 20
      volumes:
        - name: teleai-data
          persistentVolumeClaim:
            claimName: {app_name}-data-pvc
        - name: teleai-benchmark
          persistentVolumeClaim:
            claimName: {app_name}-benchmark-pvc
        - name: teleai-evaluate
          persistentVolumeClaim:
            claimName: {app_name}-evaluate-pvc
"""

    services_doc = f"""apiVersion: v1
kind: Service
metadata:
  name: telert-web
  namespace: {namespace}
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: {app_name}
    app.kubernetes.io/component: web
  ports:
    - name: http
      port: 80
      targetPort: 3000
---
apiVersion: v1
kind: Service
metadata:
  name: telert-bff
  namespace: {namespace}
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: {app_name}
    app.kubernetes.io/component: bff
  ports:
    - name: http
      port: 9000
      targetPort: 9000
---
apiVersion: v1
kind: Service
metadata:
  name: telert-orchestrator
  namespace: {namespace}
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: {app_name}
    app.kubernetes.io/component: orchestrator
  ports:
    - name: http
      port: 9001
      targetPort: 9001
"""

    ingress_doc = f"""apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {app_name}
  namespace: {namespace}
  annotations:
    nginx.ingress.kubernetes.io/proxy-body-size: 50m
spec:
  ingressClassName: {ingress_class}
{tls_block}  rules:
    - host: {domain}
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: telert-bff
                port:
                  number: 9000
          - path: /
            pathType: Prefix
            backend:
              service:
                name: telert-web
                port:
                  number: 80
"""

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "00-namespace.yaml": namespace_doc,
        "01-configmap.yaml": configmap_doc,
        "02-secret.yaml": secret_doc,
        "03-pvc.yaml": pvc_docs,
        "04-deployments.yaml": deployments_doc,
        "05-services.yaml": services_doc,
        "06-ingress.yaml": ingress_doc,
    }
    for name, content in files.items():
        (out_dir / name).write_text(content.strip() + "\n", encoding="utf-8")

    apply_script = out_dir / "apply.sh"
    apply_script.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\n"
        "kubectl apply -f \"$DIR/00-namespace.yaml\"\n"
        "kubectl apply -f \"$DIR/01-configmap.yaml\"\n"
        "kubectl apply -f \"$DIR/02-secret.yaml\"\n"
        "kubectl apply -f \"$DIR/03-pvc.yaml\"\n"
        "kubectl apply -f \"$DIR/04-deployments.yaml\"\n"
        "kubectl apply -f \"$DIR/05-services.yaml\"\n"
        "kubectl apply -f \"$DIR/06-ingress.yaml\"\n",
        encoding="utf-8",
    )
    apply_script.chmod(0o755)

    validate_script = out_dir / "validate.sh"
    validate_script.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\n"
        "echo '[1/2] Parsing YAML documents locally'\n"
        "python - <<'PY'\n"
        "from pathlib import Path\n"
        "import sys\n"
        "try:\n"
        "    import yaml\n"
        "except Exception as exc:\n"
        "    print(f'PyYAML unavailable: {exc}', file=sys.stderr)\n"
        "    raise SystemExit(2)\n"
        "base = Path(r'" + str(out_dir) + "')\n"
        "for path in sorted(base.glob('*.yaml')):\n"
        "    with path.open('r', encoding='utf-8') as fh:\n"
        "        docs = list(yaml.safe_load_all(fh))\n"
        "    kinds = [doc.get('kind') for doc in docs if isinstance(doc, dict)]\n"
        "    print(f'{path.name}: ok docs={len(docs)} kinds={kinds}')\n"
        "PY\n"
        "if command -v kubectl >/dev/null 2>&1; then\n"
        "  if kubectl cluster-info >/dev/null 2>&1; then\n"
        "    echo '[2/2] kubectl client-side validation'\n"
        "    kubectl apply --dry-run=client -f \"$DIR/00-namespace.yaml\" >/dev/null\n"
        "    kubectl apply --dry-run=client -f \"$DIR/01-configmap.yaml\" >/dev/null\n"
        "    kubectl apply --dry-run=client -f \"$DIR/02-secret.yaml\" >/dev/null\n"
        "    kubectl apply --dry-run=client -f \"$DIR/03-pvc.yaml\" >/dev/null\n"
        "    kubectl apply --dry-run=client -f \"$DIR/04-deployments.yaml\" >/dev/null\n"
        "    kubectl apply --dry-run=client -f \"$DIR/05-services.yaml\" >/dev/null\n"
        "    kubectl apply --dry-run=client -f \"$DIR/06-ingress.yaml\" >/dev/null\n"
        "    echo 'kubectl dry-run: ok'\n"
        "  else\n"
        "    echo 'kubectl found but cluster is not reachable; skipped client-side dry-run validation'\n"
        "  fi\n"
        "else\n"
        "  echo 'kubectl not found; skipped client-side dry-run validation'\n"
        "fi\n",
        encoding="utf-8",
    )
    validate_script.chmod(0o755)

    print(f"Rendered manifests to: {out_dir}")
    print("Next steps:")
    print(f"1. Review {out_dir / '02-secret.yaml'} and ensure secret values are correct.")
    print(f"2. Run: {shlex.quote(str(out_dir / 'validate.sh'))}")
    print(f"3. Run: {shlex.quote(str(out_dir / 'apply.sh'))}")
    print(f"4. Verify: kubectl -n {namespace} get pods,svc,ingress,pvc")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
