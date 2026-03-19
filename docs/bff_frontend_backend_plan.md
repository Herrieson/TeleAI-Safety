# TeleAI-Safety 前后端建设方案（BFF 架构）

更新时间：2026-03-18

> 说明：本文件用于架构与方案设计。  
> 实时进度统一查看：`docs/project_progress.md`。

## 1. 背景与目标

当前 `TeleAI-Safety` 已具备可复现的 CLI 流程，但缺少统一的 Web 入口与任务管理能力。现有核心能力集中在三段流水线：

1. `attack`：批量生成攻击结果（jsonl + manifest）
2. `benchmark`：通用评测流水线（dataset -> model -> judge -> metric）
3. `evaluate`：ASR/FRR/MDS/Kappa 计算与报告聚合

本方案目标是在不破坏现有脚本能力的前提下，新增一套可视化前后端系统，实现：

1. 统一实验配置与执行入口
2. 长任务可观测（状态、日志、产物）
3. 指标结果可查询、可对比、可追溯

## 2. 总体架构

建议采用 **BFF + Orchestrator + Worker** 架构。

1. `Frontend (Web)`：实验创建、运行监控、结果分析
2. `BFF API`：前端适配层，请求转发与聚合
3. `Orchestrator`：任务状态机与调度核心，管理阶段执行顺序
4. `Worker`：子进程执行器，调用现有脚本并采集日志/产物
5. `Postgres`：存 run 元信息、状态、配置快照、指标索引
6. `Artifact Store`：文件系统或对象存储，存 jsonl/manifest/csv/md/png 等结果文件

## 3. 为什么用 BFF

适配性：

1. 前端需要“运行态聚合数据”（阶段状态 + 实时日志 + 指标摘要 + 产物列表），直接由 BFF 聚合最合适
2. 现有 CLI 输出偏工程化，BFF 可以稳定转换为前端所需结构
3. 后续可在不改核心脚本的情况下，持续迭代页面交互

边界约束（必须遵守）：

1. BFF 不承载核心调度逻辑
2. 核心状态机在 Orchestrator
3. Worker 只负责执行与采集，不含业务判断

## 4. 三个模块的接入设计

### 4.1 Attack 接入

复用入口：

1. `attack/run_attack_parallel.sh`
2. `attack/parallel_attack.py`

接入方式：

1. Orchestrator 下发 `RUN_ID/CONFIG_DIR/RESULTS_ROOT/MANIFEST_PATH` 环境变量
2. Worker 执行 shell 脚本并持续采集 stdout/stderr
3. 产物登记：
   - manifest：`data/attack_results/manifests/*.txt`
   - 攻击结果：`data/attack_results/<model>/<method>.jsonl`
   - 可选 timing：`*.timing.json`

### 4.2 Benchmark 接入

复用入口：

1. `benchmark/cli.py`
2. `benchmark/runners/pipeline.py`

接入方式：

1. Worker 执行 `python benchmark/cli.py --config <yaml>`
2. 支持两类场景：
   - 模型生成并评估
   - 对既有结果回放评估（`configs/run/eval_from_result/*.yaml`）
3. 产物登记：
   - `output_path`（逐样本结果）
   - `summary_path`（聚合结果）

### 4.3 Evaluate 接入

复用入口：

1. `evaluate/eval_demo.sh`
2. `evaluate/evaluate_metrics.py`

接入方式：

1. Orchestrator 传入 `RESULTS_DIR` 或 `RESULT_MANIFEST`
2. Worker 执行批量评测脚本
3. 产物登记：
   - `evaluate/evaluation_report/asr/*`
   - `evaluate/evaluation_report/frr/*`
   - `evaluate/evaluation_report/mds/*`
   - `evaluate/evaluation_report/kappa/*`
   - `evaluate/evaluation_report/summary_overview.md` 等汇总文件

## 5. 任务模型与状态机

### 5.1 Run 模式

1. `attack_only`
2. `benchmark_only`
3. `eval_only`
4. `full_pipeline`（attack -> benchmark 可选 -> evaluate）

### 5.2 Stage 状态

1. `pending`
2. `running`
3. `succeeded`
4. `failed`
5. `canceled`

### 5.3 失败处理

1. 可按 stage 级别重试（不重跑已成功 stage）
2. 记录每次 attempt 的 command/env/exit_code/log_path
3. 支持从已有 manifest 继续评测

## 6. API 设计（BFF V1）

### 6.1 核心接口

1. `POST /api/runs`：创建并启动任务
2. `GET /api/runs`：任务列表
3. `GET /api/runs/{run_id}`：任务详情
4. `POST /api/runs/{run_id}/cancel`：取消任务
5. `GET /api/runs/{run_id}/logs`：按 stage 拉取日志 tail
6. `GET /api/runs/{run_id}/artifacts`：产物列表
7. `GET /api/runs/{run_id}/metrics/summary`：指标摘要
8. `GET /api/quick-attack/methods`：Quick 方法列表
9. `GET /api/quick-attack/datasets`：Quick 数据集列表

### 6.2 扩展接口

1. `POST /api/runs/{run_id}/retry`：按 stage 重试
2. `GET /api/runs/{run_id}/logs/stream`：SSE 或 WebSocket 实时日志
3. `GET /api/artifacts/{artifact_id}/download`：产物下载
4. `GET /api/runs/{run_id}/metrics/by-model`：按模型聚合
5. `GET /api/runs/{run_id}/metrics/by-attack`：按攻击方法聚合
6. `GET /api/compare?run_ids=a,b`：多 run 对比

## 7. 数据库设计（V1）

### 7.1 核心表

1. `runs`
   - `id`, `name`, `mode`, `status`, `created_by`, `created_at`, `started_at`, `ended_at`
2. `run_stages`
   - `id`, `run_id`, `stage`, `status`, `attempt`, `exit_code`, `command`, `log_path`, `started_at`, `ended_at`
3. `run_configs`
   - `run_id`, `attack_config_dir`, `benchmark_config_path`, `eval_profile`, `env_snapshot_json`
4. `artifacts`
   - `id`, `run_id`, `stage`, `type`, `path`, `size_bytes`, `checksum`, `created_at`
5. `metrics_summary`
   - `id`, `run_id`, `model`, `attack_method`, `scorer`, `asr`, `asr_effective`, `frr`, `mds`, `kappa`, `raw_json`

### 7.2 主追踪键

统一使用 `run_id + manifest_path` 关联跨阶段结果，避免错配。

## 8. 前端页面规划（V1）

1. 实验创建页
   - 选择 attack config 目录、benchmark 配置、evaluate profile/scorers
2. 运行监控页
   - stage 时间线、状态灯、实时日志、取消/重试
3. 结果总览页
   - 指标卡片、模型维度与攻击维度筛选
4. 产物中心页
   - manifest/jsonl/csv/md/png 下载与跳转
5. 对比页
   - 多 run 的 ASR/FRR/MDS/Kappa 横向对比

### 8.1 信息架构（导航）

1. `Runs`：任务列表与筛选
2. `New Run`：创建实验任务
3. `Run Detail`：阶段状态、日志、产物、指标
4. `Compare`：多 run 指标对比（规划）

### 8.2 Run Detail 页签设计

1. `Overview`
   - run 状态、阶段耗时、失败原因、关键配置快照
2. `Logs`
   - 按 stage 查看日志（attack/benchmark/evaluate）
   - 支持 tail 行数与自动刷新
3. `Artifacts`
   - 文件类型、路径、大小、生成时间
4. `Metrics`
   - run 级 summary（ASR/ASR_effective/FRR）

### 8.3 前端接口映射（当前后端）

1. 任务列表：`GET /api/runs`
2. 创建任务：`POST /api/runs`
3. 任务详情：`GET /api/runs/{run_id}`
4. 取消任务：`POST /api/runs/{run_id}/cancel`
5. 日志查看：`GET /api/runs/{run_id}/logs`
6. 产物查看：`GET /api/runs/{run_id}/artifacts`
7. 指标摘要：`GET /api/runs/{run_id}/metrics/summary`

### 8.6 Quick Attack（已落地）

前端 `New Run` 页已简化为 Quick Attack 模式：

1. 输入 `OpenAI Base URL`
2. 输入 `OpenAI API Key`
3. 输入 `Target Model Name`
4. 多选攻击方法
5. 点击开始后，后端自动生成 `attack/config`（按方法拆分 yaml）并执行
6. 攻击方法列表由后端动态返回，避免前端漏展示

后端 payload 关键字段：

1. `quick_attack_enabled=true`
2. `quick_target_model_name`
3. `quick_openai_base_url`
4. `quick_openai_api_key`（仅内存保存，不回传）
5. `quick_attack_methods`
6. `quick_dataset_key`

### 8.4 推荐前端技术栈

当前已落地：

1. `Next.js + TypeScript`
2. `Tailwind CSS`
3. React Hooks + fetch API 封装

规划增强：

1. `TanStack Query`（接口状态管理）
2. `Zustand`（轻量 UI 状态）
3. `ECharts`（指标图表）

### 8.5 详细设计文档

详见：
1. `docs/frontend_ui_plan.md`

## 9. 实施计划

### Phase 0：准备

目标：明确技术栈与运行边界，建立最小骨架。

1. 确定技术栈：`FastAPI + Celery/RQ + Redis + Postgres + React/Next.js`
2. 新建目录：`services/bff`, `services/orchestrator`, `web`
3. 约定运行用户、日志目录、产物目录、环境变量加载规则

验收标准：

1. 服务空壳可启动
2. 健康检查接口可用

### Phase 1：打通 Attack

目标：从 UI 点击到 attack 任务落地执行、可看日志、可拿产物。

1. 实现 `POST /api/runs`（仅 `attack_only`）
2. Orchestrator 调用 `attack/run_attack_parallel.sh`
3. 采集并持久化日志
4. 扫描并登记 manifest 与结果 jsonl

验收标准：

1. 可创建并执行 attack 任务
2. 可在前端看到轮询日志与最终产物列表

### Phase 2：接入 Evaluate

目标：形成 `attack -> evaluate` 闭环。

1. 支持 `eval_only` 与 `full_pipeline`
2. 复用 manifest 或 results_dir 触发 `evaluate/eval_demo.sh`
3. 解析 summary 报告入库 `metrics_summary`

验收标准：

1. 前端可查看 ASR/FRR/MDS/Kappa 摘要
2. 可查询 evaluation_report 产物路径与摘要

### Phase 3：接入 Benchmark

目标：支持 benchmark 单跑与插入 full pipeline。

1. 支持 benchmark config 模板选择
2. 调用 `benchmark/cli.py` 并登记 output/summary
3. 增加 benchmark 结果展示卡片

验收标准：

1. benchmark 任务可独立运行
2. output 与 summary 可追踪（下载接口后续补齐）

### Phase 4：体验完善

目标：达到团队可用版本。

1. 对比页（多 run）
2. 失败重试与取消增强
3. 基础权限与审计日志
4. 告警（任务失败钉钉/飞书/邮件任选）

验收标准：

1. 主要流程可稳定运行
2. 关键异常可追踪可恢复

### Phase 5：前端落地

目标：交付可用 Web 界面（不依赖 Swagger）。

1. 搭建 `web` 工程骨架与路由
2. 完成 `Runs`、`New Run`、`Run Detail` 三个核心页面
3. 对接日志/产物/指标接口
4. 增加轮询刷新与错误提示

验收标准：

1. 能在页面创建并跟踪 run
2. 能在页面查看日志、产物、指标摘要
3. 无需手工 curl 即可完成主流程

## 10. 风险与应对

1. 风险：长任务日志量大导致接口压力
   - 应对：日志分片存储 + 增量拉取 + SSE 背压
2. 风险：配置自由度高，容易出现运行时缺环境变量
   - 应对：任务创建时做配置预校验与环境变量检查
3. 风险：文件路径不统一导致评估找不到输入
   - 应对：强制 run 内路径规范化，并持久化绝对路径快照

## 11. V1 非目标

1. 不改 attack/benchmark/evaluate 内部算法逻辑
2. 不在 V1 引入复杂多租户配额系统
3. 不做跨集群弹性调度（单机或小规模 worker 优先）

## 12. 下一步执行建议

1. 优先补齐 `retry`、`logs/stream`、artifact download 三个缺口接口
2. 推进 Postgres + Redis 队列化执行，解决重启丢状态与并发可控性
