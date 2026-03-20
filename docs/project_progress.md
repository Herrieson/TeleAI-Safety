# TeleAI-Safety 前后端项目进度（唯一进度文档）

更新时间：2026-03-20

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

## 6. UI 体验升级专项进度清单（2026-03-20 启动）

1. [x] 明确评审意见并沉淀升级方案（2026-03-20）
2. [x] 完成 UI 基线审计（全局样式、三大页面、核心组件）
3. [x] 完成 Design Token 收敛（颜色/字体/圆角/间距/阴影）
4. [x] 完成 Runs 页面改造（层级、状态可读性、异常提示）
5. [x] 完成 New Run 页面改造（表单分区、提交反馈、风险提示）
6. [x] 完成 Run Detail 页面改造（概览分组、日志区可读性、指标卡样式）
7. [x] 补齐空态/错误态/弱网态反馈
8. [x] 统一动效节奏并清理冗余动画
9. [x] 完成性能优化与回归（渲染、轮询影响、滚动体验）
10. [x] 完成响应式与可访问性验收（桌面/移动）
11. [ ] 评审验收与上线发布
