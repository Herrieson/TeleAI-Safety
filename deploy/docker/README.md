# TeleAI-Safety Docker images

这个目录把“长期对外部署”需要的镜像准备工作尽量做简单了。

包含两个镜像：
1. `teleai-python-services`
   - 同一个镜像跑 `bff` 和 `orchestrator`
   - Kubernetes 里通过不同 command 区分
2. `teleai-web`
   - Next.js 生产镜像
   - 默认按同域 `/api` 方案工作

## 一次性构建

```bash
bash deploy/docker/build_images.sh registry.example.com/team latest
```

如果要顺便推送：

```bash
PUSH=1 bash deploy/docker/build_images.sh registry.example.com/team latest
```

构建完成后会打印：
- `PYTHON_SERVICES_IMAGE=...`
- `WEB_IMAGE=...`

把这两个值填进：
- `deploy/k8s/deploy.env`

## 说明

1. `teleai-web` 镜像默认不写死 `NEXT_PUBLIC_BFF_BASE_URL`
   - 这样前端会使用相对路径 `/api/*`
   - 适合长期的 Ingress 同域部署
2. `teleai-python-services` 镜像会包含整个仓库
   - 因为 orchestrator 运行时会访问仓库内脚本、benchmark、evaluate 等目录
3. 当前更适合：
   - web 可扩容
   - bff 单副本
   - orchestrator 单副本
