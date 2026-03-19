# BFF 开发迭代计划（路线图）

> 说明：本文件只维护“迭代路线图”，不维护实时进度。  
> 实时进度统一查看：`docs/project_progress.md`。

## Iteration A：基础执行链路

目标：

1. 形成 run 生命周期管理能力
2. 打通 `attack` 执行与日志/产物采集

任务：

1. run 基础接口（create/list/get/cancel）
2. stage 状态机与执行器
3. 日志 tail 接口与产物登记

## Iteration B：评测接入

目标：

1. 接入 `evaluate` 与指标摘要
2. 支持 `benchmark` 基础执行

任务：

1. `evaluate/eval_demo.sh` 链路接入
2. `summary_long.csv` 聚合为 run 级摘要
3. `benchmark` 有配置执行、无配置跳过

## Iteration C：前端 MVP

目标：

1. 交付可用 Web 操作入口

任务：

1. `Runs` 页面
2. `New Run`（Quick Attack）
3. `Run Detail`（Overview/Logs/Artifacts/Metrics）

## Iteration D：稳定性增强

目标：

1. 提升可用性与可运维性

任务：

1. `retry` 接口
2. `logs/stream`（SSE）
3. artifact 下载接口
4. Postgres 持久化
5. Redis 队列化执行
6. 鉴权与审计
