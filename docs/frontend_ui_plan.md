# TeleAI-Safety 前端界面实施计划（MVP）

更新时间：2026-03-18

> 说明：本文件用于前端页面与交互设计。  
> 实时进度统一查看：`docs/project_progress.md`。

## 1. 目标与范围

前端 MVP 目标：

1. 替代手工 curl/Swagger 的日常操作
2. 支持 run 创建、状态跟踪、日志查看、产物查看、指标查看
3. 为后续对比分析与报表能力预留页面结构

MVP 页面：

1. `Runs`（任务列表）
2. `New Run`（Quick Attack 创建）
3. `Run Detail`（总览/日志/产物/指标）

## 2. 页面能力说明

### 2.1 Runs 页面

1. run 名称、模式、状态、阶段摘要、更新时间
2. 状态筛选：`all/running/succeeded/failed/canceled`
3. 自动轮询刷新（5 秒）
4. 支持取消 `pending/running` 任务

### 2.2 New Run 页面（Quick Attack）

表单字段：

1. `name`（可选）
2. `quick_target_model_name`
3. `quick_openai_base_url`
4. `quick_openai_api_key`
5. `quick_attack_methods`（多选，支持 Select All/Clear）
6. `quick_dataset_key`（下拉选择）

数据来源：

1. `GET /api/quick-attack/methods`：动态方法列表
2. `GET /api/quick-attack/datasets`：数据集名称列表（后端维护名称到路径映射）

提交行为：

1. `mode=attack_only`
2. `quick_attack_enabled=true`
3. 后端自动生成每个方法的 attack yaml 并执行

### 2.3 Run Detail 页面

页签：

1. `Overview`：run 配置快照 + 阶段时间线 + 错误信息
2. `Logs`：按 stage 查看日志，支持 tail 行数选择（200/500/1000），3 秒轮询
3. `Artifacts`：展示类型、路径、大小、时间
4. `Metrics`：展示 `metric_summary`（如 ASR/FRR 聚合）

## 3. 实际组件清单

当前组件：

1. `RunStatusBadge`
2. `StageTimeline`
3. `RunTable`
4. `ArtifactTable`
5. `MetricCards`

## 4. 接口映射（当前 BFF）

1. `GET /api/runs`
2. `POST /api/runs`
3. `GET /api/runs/{run_id}`
4. `POST /api/runs/{run_id}/cancel`
5. `GET /api/runs/{run_id}/logs?stage=...&tail_lines=...`
6. `GET /api/runs/{run_id}/artifacts`
7. `GET /api/runs/{run_id}/metrics/summary`
8. `GET /api/quick-attack/methods`
9. `GET /api/quick-attack/datasets`

## 5. 状态管理与刷新策略（当前）

1. 使用 React Hooks + `fetch` 封装（`web/src/lib/api.ts`）
2. 列表页轮询：5 秒
3. 详情页 overview 轮询：3 秒
4. 日志页轮询：3 秒

## 6. 验收标准（MVP）

1. 可在页面发起 Quick Attack 任务
2. 可在页面查看阶段状态变化
3. 可查看日志、产物、指标摘要
4. 失败任务有清晰错误展示

## 7. 后续增强项（未落地）

1. SSE 实时日志（替代轮询）
2. 产物下载与预览
3. 多 run 对比页面
4. 鉴权、RBAC 与审计日志
5. 引入 TanStack Query（可选）
