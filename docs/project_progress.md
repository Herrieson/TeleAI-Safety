# TeleAI-Safety 前后端项目进度（唯一进度文档）

更新时间：2026-03-18

> 约定：项目进度只在本文件维护。  
> 其他文档（方案/设计/计划）不再重复维护进度状态，避免口径不一致。

## 1. 总体里程碑

1. [x] Phase 0：服务骨架（orchestrator + bff）完成
2. [x] Phase 1：`attack` 执行链路打通（日志/产物）完成
3. [x] Phase 2：`evaluate` 接入与指标摘要完成
4. [x] Phase 3：`benchmark` MVP（有配置执行、无配置跳过）完成
5. [x] Phase 4：前端 MVP（Runs/New Run/Run Detail）完成
6. [ ] Phase 5：稳定性与治理能力（进行中）

## 2. 当前已落地能力

### 2.1 Backend（Orchestrator/BFF）

1. run 生命周期接口：创建、列表、详情、取消
2. 三阶段执行框架：`attack` / `benchmark` / `evaluate`
3. 日志接口：按 stage tail 拉取
4. 产物接口：run 级 artifacts 列表
5. 指标接口：`metrics/summary`（来自 evaluate 报告聚合）
6. Quick Attack：
   - 动态攻击方法发现：`GET /api/quick-attack/methods`
   - 数据集下拉列表：`GET /api/quick-attack/datasets`
   - 运行时自动生成每个方法配置并执行
   - 前端仅传 `quick_dataset_key`，路径映射由后端维护

### 2.2 Frontend（Web）

1. `Runs`：列表、筛选、自动刷新、取消任务
2. `New Run`：Quick Attack 表单（模型、base_url、api_key、方法多选、数据集下拉）
3. `Run Detail`：Overview / Logs / Artifacts / Metrics

## 3. 当前未落地能力（Gap）

1. `POST /api/runs/{run_id}/retry`
2. `GET /api/runs/{run_id}/logs/stream`（SSE/WebSocket）
3. `GET /api/artifacts/{artifact_id}/download`
4. 持久化存储（当前 run/secret 为 in-memory）
5. 队列化执行（当前为进程内线程 + 子进程）
6. 鉴权、RBAC、审计日志
7. 多 run 对比页面与指标聚合查询（by-model/by-attack）

## 4. 下一步优先级（建议）

1. 补齐 `retry`、`logs/stream`、artifact download 三个接口
2. 引入 Postgres + Redis 队列化执行
3. 增加基础鉴权与审计
4. 增强前端结果分析与多 run 对比

## 5. 相关文档

1. 架构方案：`docs/bff_frontend_backend_plan.md`
2. 前端实现计划：`docs/frontend_ui_plan.md`
3. 迭代拆解：`docs/bff_iteration_plan.md`
