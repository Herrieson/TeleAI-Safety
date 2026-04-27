# TeleAI-Safety 小白部署教程（只有 Service 页面时）

适用场景：

1. 你现在的平台前端只能创建 `Service`
2. `Service` 只有 `ClusterIP` / `NodePort`
3. 你只是想先把当前 TeleAI-Safety 临时对外开放

这不是长期正式方案，但可以先跑通。

## 一、先理解要暴露哪两个端口

你只需要暴露两个服务：

1. `web`：前端页面，端口 `3000`
2. `bff`：后端 API，端口 `9000`

不要暴露：

3. `orchestrator`：端口 `9001`

原因：`9001` 只给系统内部用，不给外部用户直接访问。

## 二、在平台页面创建第 1 个 Service：web

填写：

1. 类型：`NodePort`
2. 名称：`telert-web`
3. 描述：`TeleAI Safety web`
4. 标签选择器：填写当前这个 TeleAI-Safety Pod 的标签
5. 端口：
   - 名称：`http`
   - 服务端口：`3000`
   - 目标 Pod 端口：`3000`
   - NodePort：
     - 能手填就填 `30080`
     - 不能手填就留空，让平台自动分配

## 三、在平台页面创建第 2 个 Service：bff

填写：

1. 类型：`NodePort`
2. 名称：`telert-bff`
3. 描述：`TeleAI Safety bff`
4. 标签选择器：和 `telert-web` 完全一样
5. 端口：
   - 名称：`http`
   - 服务端口：`9000`
   - 目标 Pod 端口：`9000`
   - NodePort：
     - 能手填就填 `30900`
     - 不能手填就留空，让平台自动分配

## 四、标签选择器怎么填

`telert-web` 和 `telert-bff` 都要指向同一个正在运行的 TeleAI-Safety Pod。

所以：

1. 去平台里找到这个 Pod / 工作负载
2. 查看它的 labels
3. 从里面挑 1 到 2 个“稳定且能唯一指向这个 Pod”的标签填进 Service 选择器
4. `web` 和 `bff` 的标签选择器必须一样

注意：

- 不一定要把所有 labels 全填进去
- 只要选择器能匹配到当前这个 Pod 就可以
- 优先选看起来稳定的标签，比如 `app=...`、`component=...`、`workspace=...`
- 在当前这类 Notebook 平台里，如果管理员明确告诉你有 `notebook-name=job-22ad2dbd3b55-20260409022144` 这种标签，通常就可以直接用它做 selector
- 尽量不要选明显像临时值的标签，比如随机 ID、一次性任务号、很长的 hash

当前这个环境可优先尝试下面两种 selector 写法。

写法 1：只用 1 个标签

- `notebook-name=job-22ad2dbd3b55-20260409022144`

写法 2：用管理员确认过的 2 个 Volcano/Notebook 标签

- `volcano-job-name=job-22ad2dbd3b55-20260409022144`
- `volcano.sh/job-type=notebook`

也就是 `telert-web` 和 `telert-bff` 两个 Service 都先填同一个 selector。优先推荐直接填管理员刚确认过的这两个：

- `volcano-job-name = job-22ad2dbd3b55-20260409022144`
- `volcano.sh/job-type = notebook`

如果创建后 Service 的 Endpoints / 后端 Pod 不是空的，就说明这个 selector 填对了。

后续如果你还会继续创建开发机 / 任务，最好在创建页面手动加一个你自己定义的稳定标签，例如：

- `service-group=teleai-safety`

这样以后在“集群服务管理”里就可以直接复用这个标签，不用每次再去问管理员。

## 五、创建完 Service 后，记下 3 个信息

你需要知道：

1. 外部访问主机地址
   - 比如：`1.2.3.4`
   - 或者：`example.com`
2. `web` 的 NodePort
   - 比如：`30080`
3. `bff` 的 NodePort
   - 比如：`30900`

如果平台自动分配了别的端口，就记实际值。

## 六、回到服务器里执行启动命令

进入项目目录：

```bash
cd /workplace/hyx/TeleAI-Safety
```

先停掉旧服务：

```bash
bash scripts/dev_down.sh
```

再按“你的实际外部地址”启动：

```bash
PUBLIC_HOST=<你的外部IP或域名> \
WEB_PUBLIC_PORT=<web的NodePort> \
BFF_PUBLIC_PORT=<bff的NodePort> \
bash scripts/dev_up_nodeport.sh
```

例子：

```bash
PUBLIC_HOST=1.2.3.4 \
WEB_PUBLIC_PORT=30080 \
BFF_PUBLIC_PORT=30900 \
bash scripts/dev_up_nodeport.sh
```

## 七、部署完成后怎么访问

浏览器打开：

```text
http://<你的外部IP或域名>:<web的NodePort>/runs
```

比如：

```text
http://1.2.3.4:30080/runs
```

页面里的接口会自动去请求：

```text
http://<你的外部IP或域名>:<bff的NodePort>/api/...
```

## 八、如果打不开，重点检查这 4 项

1. `web` Service 是否真的是 `NodePort`
2. `bff` Service 是否真的是 `NodePort`
3. 两个 Service 的标签选择器是否真的选中了当前 Pod
4. 重启时填的 host 和 NodePort 是否与平台页面显示的一致

## 九、最简单的推荐值

如果平台允许手填 NodePort，就直接用：

1. `telert-web`：`3000 -> 3000`，NodePort=`30080`
2. `telert-bff`：`9000 -> 9000`，NodePort=`30900`

启动命令：

```bash
cd /workplace/hyx/TeleAI-Safety
bash scripts/dev_down.sh
PUBLIC_HOST=<你的IP或域名> WEB_PUBLIC_PORT=30080 BFF_PUBLIC_PORT=30900 bash scripts/dev_up_nodeport.sh
```

## 十、日后继续开发怎么做

日常开发时，最简单的流程就是：

1. 进入项目目录：`cd /workplace/hyx/TeleAI-Safety`
2. 保持现在这个 NodePort 启动方式不变
3. 直接改代码
4. 改完后刷新浏览器，继续访问：`http://116.238.240.2:31587/runs`

为什么可以直接改：

- `web` 现在是 `next dev`，前端代码修改后通常会自动热更新
- `bff` 和 `orchestrator` 现在是 `uvicorn --reload`，Python 代码修改后通常会自动重载

如果你只是改代码，通常不用重新创建 Service，也不用每次都手动重启。

### 什么时候需要重启

下面这些情况再重启就行：

1. 你改了启动相关环境变量
2. 自动热更新没有生效
3. 页面明显异常，想强制重启一遍
4. 你重建了开发机 / Pod，或者 NodePort 变了

重启命令：

```bash
cd /workplace/hyx/TeleAI-Safety
bash scripts/dev_down.sh
PUBLIC_HOST=116.238.240.2 WEB_PUBLIC_PORT=31587 BFF_PUBLIC_PORT=31103 bash scripts/dev_up_nodeport.sh
```

### 什么时候需要重新找管理员

只有下面几种情况才需要：

1. 你重新创建了开发机 / Notebook
2. 原来的 Service 没了
3. NodePort 变了
4. 外部访问 IP / 域名变了

这时就让管理员重新确认：

- `volcano-job-name=job-22ad2dbd3b55-20260409022144`
- `volcano.sh/job-type=notebook`

并重新给 `3000` 和 `9000` 建 NodePort。

## 十一、记住一句话

只暴露两个：

1. `3000`（web）
2. `9000`（bff）

不要暴露：

3. `9001`（orchestrator）
