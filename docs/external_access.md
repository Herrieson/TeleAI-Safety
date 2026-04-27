# TeleAI-Safety external access

推荐的外部部署拓扑：

1. `orchestrator` 仅监听内网/本机，不对公网暴露
2. `bff` 仅通过反向代理对外提供 `/api/`
3. `web` 通过同一个公网域名提供 `/`
4. 由 Nginx / Ingress 统一暴露 `80/443`

## 推荐启动方式

在仓库根目录：

```bash
ORCH_BIND_HOST=127.0.0.1 \
BFF_BIND_HOST=127.0.0.1 \
WEB_BIND_HOST=127.0.0.1 \
BFF_CORS_ALLOW_ORIGINS=https://teleai.example.com \
NEXT_PUBLIC_BFF_BASE_URL= \
bash scripts/dev_up.sh
```

说明：

1. `NEXT_PUBLIC_BFF_BASE_URL` 置空时，前端使用相对路径 `/api/*`
2. 反向代理需要将 `/api/` 转发到 `127.0.0.1:9000`
3. `orchestrator` 继续只由 `bff` 通过 `http://127.0.0.1:9001` 访问

如果不走同域反代，而是让浏览器直接访问 BFF：

```bash
ORCH_BIND_HOST=127.0.0.1 \
BFF_BIND_HOST=0.0.0.0 \
WEB_BIND_HOST=0.0.0.0 \
BFF_CORS_ALLOW_ORIGINS=https://teleai.example.com \
NEXT_PUBLIC_BFF_BASE_URL=https://teleai.example.com:9000 \
bash scripts/dev_up.sh
```

但不建议长期直接暴露 `9000`，更不要暴露 `9001`。

## 关键环境变量

1. `ORCH_BIND_HOST` / `ORCH_PORT`
2. `BFF_BIND_HOST` / `BFF_PORT`
3. `WEB_BIND_HOST` / `WEB_PORT`
4. `NEXT_PUBLIC_BFF_BASE_URL`
5. `BFF_CORS_ALLOW_ORIGINS`
6. `ORCHESTRATOR_BASE_URL`（默认 `http://127.0.0.1:9001`）

## 反向代理

可直接使用 `deploy/nginx/teleai-external.conf` 作为模板。

## 只有 Service 页面时的临时方案

如果当前平台前端只能创建 `ClusterIP` / `NodePort` Service，而没有 Ingress / 网关 / 域名配置入口，那么只能先做临时直连方案：

1. `web` 建一个 `NodePort`，转发到容器 `3000`
2. `bff` 建一个 `NodePort`，转发到容器 `9000`
3. `orchestrator` 不对外暴露
4. 前端 `NEXT_PUBLIC_BFF_BASE_URL` 必须改成外部可达的 BFF 地址
5. `BFF_CORS_ALLOW_ORIGINS` 必须改成外部可达的 web 地址

仓库中可直接使用：

```bash
bash scripts/dev_up_nodeport.sh
```

在当前这类 Notebook/Volcano 平台里，Service selector 可优先使用管理员确认过的稳定标签，例如：

- `volcano-job-name=<你的job名>`
- `volcano.sh/job-type=notebook`

如果后续会频繁创建开发机/任务，建议在创建页面额外自定义一个稳定标签（例如 `service-group=teleai-safety`），这样之后创建 Service 时就能直接复用。

详细页面填写方式、NodePort 示例和启动命令见：

- `docs/service_page_nodeport.md`
- `docs/service_page_quickstart.md`
