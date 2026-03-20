# TeleAI-Safety 前端界面实施计划（MVP）

更新时间：2026-03-20

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

## 8. UI 体验升级专项方案（领导评审意见响应）

专项背景（2026-03-20）：

1. 领导反馈：界面需同时满足“美观、科技感、人机交互舒适、流畅”
2. 本专项目标：在不改变核心业务流程的前提下，升级视觉与交互质量，并约束性能指标

### 8.1 升级目标定义（四维）

1. 美观：统一视觉规范，提升排版层级与页面秩序感
2. 科技感：形成稳定的品牌视觉语言（色彩、光感、数据化元素、动效节奏）
3. 交互舒适：操作反馈明确、信息可预期、关键任务路径更短
4. 流畅：页面切换、列表滚动、状态刷新无明显卡顿

### 8.2 设计与实现策略

1. 视觉策略：
   - 统一 Design Token（颜色、字体、圆角、阴影、间距、边框）
   - 强化首屏信息层级（主标题、关键状态、主操作）
   - 背景与卡片维持轻量科技质感，避免过度装饰影响可读性
2. 交互策略：
   - 所有关键操作补齐反馈链路：hover -> click -> loading -> success/error
   - 核心流程减少重复确认和来回跳转
   - 补齐空态、异常态、弱网态文案与交互引导
3. 性能策略：
   - 控制首屏渲染负担，避免无意义重渲染
   - 动效统一 150-300ms，确保可感知但不拖慢
   - 保持轮询策略可用，同时优化局部刷新范围

### 8.3 页面级改造范围（落地到代码）

1. 全局样式层：`web/src/app/globals.css`、`web/src/app/layout.tsx`
   - 统一 Token 命名与使用
   - 统一按钮、输入框、卡片、标签页状态样式
2. Runs 页面：`web/src/app/runs/page.tsx`、`web/src/components/runs/RunTable.tsx`、`web/src/components/runs/RunStatusBadge.tsx`
   - 强化统计区、筛选区、列表区层级
   - 优化状态色与异常提示可读性
3. New Run 页面：`web/src/app/runs/new/page.tsx`
   - 复杂表单分区（基础配置/攻击配置/评测配置）
   - 强化提交前校验提示与风险提示
4. Run Detail 页面：`web/src/app/runs/[runId]/page.tsx`、`web/src/components/runs/StageTimeline.tsx`、`web/src/components/runs/MetricCards.tsx`、`web/src/components/runs/ArtifactTable.tsx`
   - 优化概览信息分组和时间线可读性
   - 提升日志区可读性与操作效率（tail/stage 选择）

### 8.4 里程碑与交付节奏

1. M1（D1-D2）：UI 基线审计与 Token 收敛方案
2. M2（D3-D5）：Runs/New Run 视觉与交互改造
3. M3（D6-D8）：Run Detail 改造与状态反馈补齐
4. M4（D9-D10）：动效统一、性能优化、响应式验收

### 8.5 验收标准（专项）

1. 一致性：
   - 核心页面组件 100% 使用统一样式变量（不再出现散落硬编码风格）
2. 交互舒适：
   - 关键按钮点击后 100ms 内出现反馈（loading/状态变化）
   - 核心任务路径（创建 run 并查看详情）无阻塞性提示缺失
3. 流畅性：
   - 页面切换无明显掉帧
   - 长列表与日志滚动连续性明显优于当前版本
4. 兼容性：
   - 桌面与移动端（窄屏）均可完成核心流程
