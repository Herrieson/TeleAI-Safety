# TeleAI Web (MVP)

## Quick Start

在仓库根目录确保后端服务已启动：

1. Orchestrator: `http://127.0.0.1:9001`
2. BFF: `http://127.0.0.1:9000`

再启动前端：

```bash
cd web
cp .env.example .env.local
npm install
npm run dev
```

如需直接从浏览器访问独立 BFF 端口，请在 `.env.local` 中设置：

```bash
NEXT_PUBLIC_BFF_BASE_URL=http://127.0.0.1:9000
```

如需走同域名反向代理（推荐），可不设置该变量，前端会直接请求相对路径 `/api/*`。

默认访问：

1. `http://127.0.0.1:3000/runs`
2. `http://127.0.0.1:3000/runs/new`

`/runs/new` 为 Quick Attack 模式，最少只需：

1. Target Model Name
2. OpenAI Base URL
3. OpenAI API Key
4. 选择攻击方法

## 环境变量

1. `NEXT_PUBLIC_BFF_BASE_URL`：BFF 服务地址；留空/不设置时，前端默认使用同域 `/api/*`
