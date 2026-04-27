# TeleAI-Safety Kubernetes quickstart

这是一份给正式长期部署用的最短说明。

目标架构：
- 外部只暴露一个域名
- `/` -> web
- `/api` -> bff
- `orchestrator` 只在集群内，不暴露公网

## 为什么推荐这样做

1. 前端天然支持同域 `/api`
2. 不需要把 orchestrator 暴露到公网
3. 比长期使用 NodePort 更干净，也更容易接 TLS / WAF / 域名
4. 更适合后续继续开发和维护

## 你现在只需要做这 6 步

### 1) 构建镜像

```bash
bash deploy/docker/build_images.sh registry.example.com/team latest
```

如果还要推送镜像：

```bash
PUSH=1 bash deploy/docker/build_images.sh registry.example.com/team latest
```

### 2) 复制参数模板

```bash
cp deploy/k8s/deploy.env.example deploy/k8s/deploy.env
```

### 3) 只改最关键的几个值

至少改这些：
- `NAMESPACE`
- `DOMAIN`
- `PYTHON_SERVICES_IMAGE`
- `WEB_IMAGE`
- `TLS_SECRET_NAME`（启用 TLS 时）
- `STORAGE_CLASS`（你的集群需要显式指定时）

另外建议确认：
- `BFF_CORS_ALLOW_ORIGINS=https://你的域名`
- `NEXT_PUBLIC_BFF_BASE_URL=` 保持为空
- `ORCHESTRATOR_BASE_URL=http://telert-orchestrator:9001`

### 4) 生成 K8s YAML

```bash
python deploy/k8s/generate.py --env-file deploy/k8s/deploy.env
```

默认会输出到：
- `deploy/k8s/rendered/`

### 5) 先校验，再 apply

```bash
bash deploy/k8s/rendered/validate.sh
bash deploy/k8s/rendered/apply.sh
```

### 6) 查看部署结果

```bash
kubectl -n <namespace> get pods,svc,ingress,pvc
```

## 当前模板会生成什么

- Namespace
- ConfigMap
- Secret
- 3 个 PVC
- 3 个 Deployment
- 3 个 ClusterIP Service
- 1 个 Ingress
- `validate.sh`
- `apply.sh`

## 当前默认策略

- `web`：可后续扩容
- `bff`：先 1 副本
- `orchestrator`：先 1 副本

原因：
- orchestrator 当前有本地状态与落盘状态
- bff 的部分 managed mode 状态也在进程内

## 验收标准

部署完成后，至少确认：
- `https://你的域名/runs` 能打开
- `https://你的域名/api/health` 正常
- 页面上的 run/list/log 等功能可用
- 公网不能直接访问 9001

## 相关文件

- `deploy/docker/README.md`
- `deploy/k8s/README.md`
- `deploy/k8s/deploy.env.example`
- `deploy/k8s/generate.py`
