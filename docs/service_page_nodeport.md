# TeleAI-Safety：只有 Service 页面时的临时对外暴露

适用前提：

1. 当前平台前端只能创建 `Service`
2. `Service` 类型只有 `ClusterIP` / `NodePort`
3. 当前 TeleAI-Safety 不是正式 K8s Deployment，而是在一个工作 Pod 里以 dev 模式运行
4. 目标是“先让外部能访问”，不是正式长期单域名上线

## 先说结论

如果只有 Service 页面，那么当前能做的是：

1. 创建一个 `telert-web` 的 `NodePort` Service，转发到容器 `3000`
2. 创建一个 `telert-bff` 的 `NodePort` Service，转发到容器 `9000`
3. 不要创建 `9001` 的对外 Service
4. 用 `scripts/dev_up_nodeport.sh` 把前端和 BFF 的外部地址配置好后重启

这只是临时方案，不是长期最佳方案。

## 为什么不能暴露 orchestrator

当前 orchestrator 只应该被 BFF 在 Pod 内访问：

1. 它监听的是 `127.0.0.1:9001`
2. 前端不会直接调用它
3. 对外暴露只会增加攻击面

所以页面上不要为 `9001` 创建 `NodePort`。

## 页面应该怎么填

### Service 1：telert-web

推荐填写：

1. 类型：`NodePort`
2. 名称：`telert-web`
3. 描述：`TeleAI Safety web`
4. 标签选择器：填写“当前这个工作 Pod”的标签
5. 端口：
   - 名称：`http`
   - 服务端口：`3000`（也可以填 `80`，但为了少绕弯，建议先填 `3000`）
   - 目标 Pod 端口：`3000`
   - NodePort：
     - 如果页面允许手填，建议用 `30080`
     - 如果页面自动分配，就留空，记住最后分配出来的端口

### Service 2：telert-bff

推荐填写：

1. 类型：`NodePort`
2. 名称：`telert-bff`
3. 描述：`TeleAI Safety bff`
4. 标签选择器：和 `telert-web` 完全一样
5. 端口：
   - 名称：`http`
   - 服务端口：`9000`
   - 目标 Pod 端口：`9000`
   - NodePort：
     - 如果页面允许手填，建议用 `30900`
     - 如果页面自动分配，就留空，记住最后分配出来的端口

### 不要创建

不要创建：

1. `telert-orchestrator` 的 `NodePort`
2. `9001` 的任何公网暴露

## 标签选择器怎么填

`telert-web` 和 `telert-bff` 都应该指向“当前这个正在跑 TeleAI-Safety 的 Pod”。

因为现在 web / bff / orchestrator 都在同一个 Pod 里跑，所以这两个 Service 的 selector 应该填一样。

从平台页面里找到当前工作负载或 Pod 的标签后，不一定要全部照抄；通常挑 1 到 2 个“稳定且能唯一匹配当前 Pod”的标签就够了，例如类似：

- `app=teleai-safety`
- `component=workspace`
- `workspace=<名字>`

注意：

1. `web` 和 `bff` 的 selector 必须一样
2. 优先选稳定标签，不要优先选随机 hash、一次性任务 ID 这类临时标签
3. 实际还是以平台上这个 Pod 的真实 labels 为准
4. 如果管理员已经明确给出类似 `notebook-name=job-22ad2dbd3b55-20260409022144` 这样的标签，在当前 Notebook 平台里通常可以优先直接用它

当前这个实例，管理员已经确认下面两组标签可用：

写法 1：

- `notebook-name = job-22ad2dbd3b55-20260409022144`

写法 2（更推荐，管理员明确确认可用）：

- `volcano-job-name = job-22ad2dbd3b55-20260409022144`
- `volcano.sh/job-type = notebook`

也就是：

- `telert-web` 的 selector 可以填：`volcano-job-name=job-22ad2dbd3b55-20260409022144` + `volcano.sh/job-type=notebook`
- `telert-bff` 的 selector 也填完全一样的两项

如果创建后 Service 的 Endpoints / 后端 Pod 不为空，说明这个 selector 是对的。

如果你后面还会反复创建开发机 / 任务，建议在创建页面自己额外加一个稳定自定义标签，例如：

- `service-group=teleai-safety`

这样以后创建 Service 时，就能直接在“集群服务管理”里复用这个自定义标签，不用每次再问管理员查 Pod labels。

## 本地已经准备好的启动方式

仓库里新增了：

- `scripts/dev_up_nodeport.sh`

它会自动做下面这些事：

1. orchestrator 保持 `127.0.0.1:9001`
2. bff 绑定到 `0.0.0.0:9000`
3. web 绑定到 `0.0.0.0:3000`
4. 把前端 `NEXT_PUBLIC_BFF_BASE_URL` 指向外部可达的 BFF 地址
5. 把 `BFF_CORS_ALLOW_ORIGINS` 设成外部可达的 web 地址

## 创建完 Service 后，怎么启动

### 方式 A：你已经知道完整外部地址

假设平台对外地址最终是：

- Web: `http://<节点IP或域名>:30080`
- BFF: `http://<节点IP或域名>:30900`

执行：

```bash
cd /workplace/hyx/TeleAI-Safety
bash scripts/dev_down.sh
WEB_PUBLIC_ORIGIN=http://<节点IP或域名>:30080 \
BFF_PUBLIC_BASE_URL=http://<节点IP或域名>:30900 \
bash scripts/dev_up_nodeport.sh
```

### 方式 B：你只知道 host 和两个 NodePort

```bash
cd /workplace/hyx/TeleAI-Safety
bash scripts/dev_down.sh
PUBLIC_HOST=<节点IP或域名> \
WEB_PUBLIC_PORT=30080 \
BFF_PUBLIC_PORT=30900 \
bash scripts/dev_up_nodeport.sh
```

如果平台自动分配的不是 `30080/30900`，就把命令里的端口替换成实际值。

## 启动完成后你应该看到的效果

1. 外部打开 `http://<host>:<web-nodeport>/runs`
2. 页面里的接口请求会直接打到 `http://<host>:<bff-nodeport>/api/...`
3. BFF 再去访问 Pod 内部的 orchestrator `127.0.0.1:9001`

## 日后继续开发怎么做

当前这套启动方式本身就是开发模式：

1. `web` 是 `next dev`
2. `bff` 是 `uvicorn --reload`
3. `orchestrator` 也是 `uvicorn --reload`

所以日常开发时：

1. 保持当前 NodePort Service 不动
2. 直接在 `/workplace/hyx/TeleAI-Safety` 改代码
3. 前端通常会自动热更新
4. Python 服务通常会自动重载
5. 浏览器继续访问当前外部地址即可

当前这次可用地址是：

- Web: `http://116.238.240.2:31587/runs`
- BFF: `http://116.238.240.2:31103/api/health`

如果热更新失效，或者你改了启动相关环境变量，就执行：

```bash
cd /workplace/hyx/TeleAI-Safety
bash scripts/dev_down.sh
PUBLIC_HOST=116.238.240.2 \
WEB_PUBLIC_PORT=31587 \
BFF_PUBLIC_PORT=31103 \
bash scripts/dev_up_nodeport.sh
```

如果后面重建了开发机 / Pod / Service，或者 NodePort 变了，就要：

1. 让管理员按同样 selector 重新建 `3000` 和 `9000` 的 NodePort
2. 把新的外部 IP/域名 和 NodePort 替换到启动命令里

## 这仍然不是长期最佳方案

真正长期正式方案仍然需要：

1. `Deployment` / 工作负载发布能力
2. `Ingress` 或反向代理能力
3. 域名和 TLS
4. `ConfigMap` / `Secret`
5. PVC 持久卷

长期推荐拓扑仍然是：

1. `web`：`ClusterIP`
2. `bff`：`ClusterIP`
3. `orchestrator`：`ClusterIP`
4. `Ingress`：
   - `/` -> `web`
   - `/api` -> `bff`

这样前端就可以把 `NEXT_PUBLIC_BFF_BASE_URL` 留空，直接走同域 `/api`。
