# Services Bootstrap (Phase 0)

该目录是 TeleAI-Safety 前后端化改造的服务层，当前包含：

1. `services/orchestrator`：任务编排服务（当前为内存版 run 管理）
2. `services/bff`：前端适配层，向 orchestrator 转发 run 相关接口

## 当前状态

当前版本是 **Phase 0 + Iteration 2(attack链路) 初版**：

1. 健康检查
2. 创建 run（后台自动启动执行）
3. 查询 run 列表与详情（含 stage 状态）
4. 取消 run（尝试终止活动子进程）
5. 查询 run 产物（manifest/jsonl/timing/log）
6. 查询 run 日志（tail）

说明：当前已实现 `attack`、`benchmark`、`evaluate` 三个 stage 的执行框架：
1. `attack`：真实调用脚本执行
2. `benchmark`：有配置就执行，无配置则跳过
3. `evaluate`：真实调用评测脚本执行，并生成指标摘要
4. 运行结果隔离：默认按 `run_id` 写入独立目录，避免不同 run 互相污染
   - attack 结果：`data/attack_results/runs/<run_id>/`
   - benchmark 结果：`benchmark/result/runs/<run_id>/`
   - evaluate 报告：`evaluate/evaluation_report/runs/<run_id>/`
   - 阶段日志与运行时配置：`data/service_runs/<run_id>/`

另外支持 Quick Attack 自动配置模式（推荐用于 UI）：

1. 前端只传 `quick_openai_base_url`、`quick_openai_api_key`、`quick_target_model_name`、`quick_attack_methods`、`quick_dataset_key`
2. Orchestrator 自动按方法生成 yaml 到运行目录
3. 自动调用 attack 并登记 manifest/jsonl 产物
4. 若配置了内部 LLM 且关闭严格隔离（`TELEAI_STRICT_CRED_ISOLATION=false`），可将前端 `quick_openai_*` 留空；系统会优先用内部凭据

内部 LLM（用于攻击链路内部模型与 evaluate）可通过环境变量配置：

1. `TELEAI_INTERNAL_LLM_API_KEY`
2. `TELEAI_INTERNAL_LLM_BASE_URL`
3. `TELEAI_INTERNAL_LLM_MODEL`（可选，默认 `gpt-4o-mini`）
4. `TELEAI_USE_INTERNAL_LLM_FOR_ATTACK`（默认 `true`）
5. `TELEAI_USE_INTERNAL_LLM_FOR_EVALUATE`（默认 `true`）
6. `TELEAI_STRICT_CRED_ISOLATION`（默认 `true`，开启后禁止从 target 凭据回退）

额外约束（防止结果污染）：

1. `mode=eval_only` 时必须显式提供 `result_manifest`
2. 未提供 `result_manifest` 的 eval-only 请求会被拒绝

## 启动方式

在仓库根目录执行：

```bash
uv run python -m uvicorn services.orchestrator.app.main:app --host 0.0.0.0 --port 9001 --reload
```

新开一个终端：

```bash
ORCHESTRATOR_BASE_URL=http://127.0.0.1:9001 \
uv run python -m uvicorn services.bff.app.main:app --host 0.0.0.0 --port 9000 --reload
```

可选：当前端与 BFF 分端口部署时，建议显式配置 CORS 来源（默认已包含 `127.0.0.1:3000` 与 `localhost:3000`）：

```bash
BFF_CORS_ALLOW_ORIGINS=http://127.0.0.1:3000,http://localhost:3000
```

## 接口

### Orchestrator

1. `GET /health`
2. `POST /v1/runs`
3. `GET /v1/runs`
4. `GET /v1/runs/{run_id}`
5. `POST /v1/runs/{run_id}/cancel`
6. `DELETE /v1/runs/{run_id}`（删除任务记录与 run 级产物目录）
7. `GET /v1/runs/{run_id}/artifacts`
8. `GET /v1/runs/{run_id}/logs?stage=attack&tail_lines=200`
9. `GET /v1/runs/{run_id}/metrics/summary`
10. `GET /v1/quick-attack/methods`
11. `GET /v1/quick-attack/datasets`

### BFF

1. `GET /health`
2. `GET /api/health`
3. `POST /api/runs`
4. `GET /api/runs`
5. `GET /api/runs/{run_id}`
6. `POST /api/runs/{run_id}/cancel`
7. `DELETE /api/runs/{run_id}`（删除任务记录与 run 级产物目录）
8. `GET /api/runs/{run_id}/artifacts`
9. `GET /api/runs/{run_id}/logs?stage=attack&tail_lines=200`
10. `GET /api/runs/{run_id}/metrics/summary`
11. `GET /api/quick-attack/methods`
12. `GET /api/quick-attack/datasets`

## 下一步

1. 增加日志流式接口（SSE）
2. 引入队列（Redis + Worker）替换进程内线程执行
3. 将本地文件快照 store（当前 `data/service_runs/_state/runs_store.json`）替换为 Postgres
4. 补齐评测结果细粒度入库（按 model/attack/scorer）

## Quick Attack 请求示例

```json
{
  "name": "quick-gpt4o-mini",
  "mode": "attack_only",
  "quick_attack_enabled": true,
  "quick_target_model_name": "gpt-4o-mini",
  "quick_openai_base_url": "https://api.openai.com/v1",
  "quick_openai_api_key": "sk-***",
  "quick_attack_methods": ["pair", "cipher", "rene"],
  "quick_dataset_key": "teleai_samples_500_500"
}
```
