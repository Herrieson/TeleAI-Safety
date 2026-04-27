# TeleAI-Safety Kubernetes quick deploy

这个目录是给“尽量小白一点”的长期部署准备的。

目标拓扑：
- 外部只访问一个域名
- `/` -> web
- `/api` -> bff
- orchestrator 只在集群内

## 你只需要做的事

### 1. 构建镜像

```bash
bash deploy/docker/build_images.sh registry.example.com/team latest
```

如果镜像仓库需要推送：

```bash
PUSH=1 bash deploy/docker/build_images.sh registry.example.com/team latest
```

### 2. 复制配置文件

```bash
cp deploy/k8s/deploy.env.example deploy/k8s/deploy.env
```

重点改这几个值：
- `NAMESPACE`
- `DOMAIN`
- `PYTHON_SERVICES_IMAGE`
- `WEB_IMAGE`
- `TLS_SECRET_NAME`（如果启用 TLS）
- `STORAGE_CLASS`（如果你的集群需要指定）

### 3. 生成 YAML

```bash
python deploy/k8s/generate.py --env-file deploy/k8s/deploy.env
```

生成结果会在：
- `deploy/k8s/rendered/`

### 4. 先做本地校验

```bash
bash deploy/k8s/rendered/validate.sh
```

这个脚本会：
- 先解析生成出的 YAML，确认格式没坏
- 如果本机有 `kubectl`，再做一次 `--dry-run=client` 校验

### 5. 应用到集群

```bash
bash deploy/k8s/rendered/apply.sh
```

### 6. 检查状态

```bash
kubectl -n <namespace> get pods,svc,ingress,pvc
```

## 生成内容说明

会生成：
- `00-namespace.yaml`
- `01-configmap.yaml`
- `02-secret.yaml`
- `03-pvc.yaml`
- `04-deployments.yaml`
- `05-services.yaml`
- `06-ingress.yaml`
- `apply.sh`

## 默认部署策略

1. `web`：ClusterIP + Ingress
2. `bff`：ClusterIP + Ingress
3. `orchestrator`：ClusterIP only，不对公网开放
4. `NEXT_PUBLIC_BFF_BASE_URL` 默认留空，前端走同域 `/api`
5. `ORCHESTRATOR_BASE_URL` 默认指向：
   - `http://telert-orchestrator:9001`

## 默认持久化目录

当前模板会给 orchestrator 挂 3 个 PVC：
1. `/app/data`
2. `/app/benchmark/result`
3. `/app/evaluate/evaluation_report`

这样至少把这些长期结果保住：
- `data/service_runs`
- `data/attack_results`
- `benchmark/result/runs`
- `evaluate/evaluation_report/runs`

## 当前推荐副本数

- `web=1`（需要时可放大）
- `bff=1`
- `orchestrator=1`

原因：
- orchestrator 当前有本地文件状态
- bff 某些 managed mode 限流状态在进程内

## 注意

1. `teleai-web` 镜像应按“同域 /api”思路构建，不要写死公网 BFF 地址
2. 如果你启用了 `ENABLE_TLS=true`，请确保 Ingress Controller / cert-manager / TLS secret 已准备好
3. `02-secret.yaml` 里如果涉及真实模型密钥，应用前先检查
4. 不要把 `telert-orchestrator` 做成 NodePort / LoadBalancer
