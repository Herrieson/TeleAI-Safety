# TeleAI-Safety 平台托管凭据方案（Model Profile + Secret Manager）

更新时间：2026-03-20

> 说明：本文件用于替代前端明文填写 `base_url/api_key` 的方案设计与实施清单。  
> 进度状态统一维护：`docs/project_progress.md`。

## 1. 背景与目标

当前 `New Run` 允许用户输入被测模型的 `base_url` 和 `api_key`。该方式存在以下问题：

1. 密钥暴露面大（前端输入、网络传输、日志误打风险）
2. 凭据管理不可治理（无统一轮换、无权限边界）
3. 审计追踪弱（难以回答“谁在何时使用了哪把密钥”）

本方案目标：

1. 用户只选择“模型配置（Model Profile）”，不接触密钥
2. 密钥托管到 Secret Manager（Vault/KMS/云密钥服务）
3. 运行时通过 `credential_id` 拉取密钥，且仅在内存短时使用
4. 前端、API 响应、run 记录、日志中不出现明文密钥

## 2. 总体架构

核心思路：`Model Profile` 与 `Credential` 解耦。

1. 前端：
   - `New Run` 页面只展示 `Target Model Profile` 下拉
2. BFF：
   - 创建 run 时只接收 `target_profile_id`
   - 从 profile 解析出 `provider/model/base_url/credential_id`
3. Orchestrator：
   - 执行前按 `credential_id` 从 Secret Manager 拉取密钥
   - 调用模型后立即清理内存敏感变量
4. Secret Manager：
   - 保存明文密钥（平台安全域）
   - 业务 DB 仅保存 `secret_ref` 或 `credential_id` 映射

## 3. 数据模型改造

### 3.1 新增表：`credentials`

建议字段：

1. `credential_id`（主键）
2. `provider`（如 `openai/azure/openrouter`）
3. `secret_ref`（Secret Manager 引用，不是明文）
4. `key_fingerprint`（用于审计展示，示例：前 6 + 后 4）
5. `status`（`active/disabled/rotating`）
6. `created_by`
7. `created_at`
8. `rotated_at`

### 3.2 新增表：`model_profiles`

建议字段：

1. `profile_id`（主键）
2. `display_name`（前端显示名）
3. `provider`
4. `model_name`
5. `base_url`
6. `credential_id`（外键 -> credentials）
7. `is_active`
8. `tags`（可选，便于筛选）
9. `created_by`
10. `created_at`

### 3.3 调整表：`runs`

建议新增字段：

1. `target_profile_id`
2. `resolved_provider`
3. `resolved_model_name`
4. `resolved_base_url`
5. `resolved_credential_id`（仅后端可见）

建议废弃字段（兼容期后移除）：

1. `quick_openai_api_key`
2. `quick_openai_base_url`（可由 profile 派生）
3. `quick_target_model_name`（可由 profile 派生）

## 4. API 改造

### 4.1 用户侧接口

1. `GET /api/model-profiles`
   - 返回可选 profile 列表（不含密钥）
2. `POST /api/runs`
   - 新增/必填：`target_profile_id`
   - 移除：`quick_openai_api_key`
   - 兼容期：允许旧字段但后端忽略并告警

### 4.2 管理侧接口（仅管理员）

1. `POST /api/admin/credentials`
   - 上送密钥到 Secret Manager，返回 `credential_id`
2. `POST /api/admin/model-profiles`
   - 创建 profile 并绑定 `credential_id`
3. `POST /api/admin/credentials/{credential_id}/rotate`
   - 轮换密钥并更新引用
4. `POST /api/admin/model-profiles/{profile_id}/disable`
   - 失效高风险或过期 profile

## 5. 运行时流程

1. 管理员创建 `credential`（密钥写入 Secret Manager）
2. 管理员创建 `model_profile`（绑定 `credential_id`）
3. 普通用户创建 run 时只选 `target_profile_id`
4. Orchestrator 获取 profile 并解析 `credential_id`
5. 执行器向 Secret Manager 拉取密钥到内存
6. 调用模型并完成任务
7. 清理内存密钥，不落盘，不写日志

## 6. 安全与治理控制

1. RBAC：普通用户无权查看/管理凭据
2. 审计：记录 run 到 `profile_id/credential_id` 的映射
3. 日志脱敏：
   - `Authorization`
   - `sk-...`
   - URL query 中疑似 token 字段
4. 最小权限：执行节点仅可读指定 secret path
5. 轮换策略：支持 `active + next` 平滑切换
6. 网络白名单：执行节点仅访问允许的模型域名

## 7. 前端改造点

目标文件：

1. `web/src/app/runs/new/page.tsx`
2. `web/src/lib/types.ts`
3. `web/src/lib/api.ts`
4. `web/src/app/runs/[runId]/page.tsx`

改造内容：

1. 删除 `api_key/base_url` 输入框
2. 新增 `Target Model Profile` 下拉
3. 提交 payload 改为 `target_profile_id`
4. 详情页展示 profile 信息，不展示凭据字段

## 8. 分阶段实施计划

### Phase A（兼容期）

1. 后端支持 `target_profile_id`，保留旧字段兼容
2. 前端切到 profile 下拉
3. 旧字段进来时记录告警日志

### Phase B（收敛期）

1. 关闭前端旧字段入口
2. 后端对旧字段返回明确废弃错误
3. 完成历史 run 字段迁移

### Phase C（治理期）

1. 强制 profile-only 模式
2. 上线凭据轮换流程与审计报表
3. 建立季度密钥巡检机制

## 9. 验收标准

1. 前端界面与 API 响应中 0 明文密钥
2. run 元数据和日志中 0 明文密钥
3. 新建 run 100% 使用 `target_profile_id`
4. 轮换后新任务走新凭据，旧任务可追溯

## 10. 任务清单（可执行）

### 10.1 架构与数据层

1. [ ] 设计并评审 `credentials/model_profiles` 表结构
2. [ ] 实现 DB migration（新增表 + runs 字段）
3. [ ] 实现 Secret Manager 适配层（Vault/KMS provider）
4. [ ] 增加凭据加解密与引用解析单元测试

### 10.2 BFF 与编排层

1. [ ] 增加 `GET /api/model-profiles`
2. [ ] 改造 `POST /api/runs` 入参与校验逻辑
3. [ ] 执行器改为按 `credential_id` 拉取密钥
4. [ ] 日志脱敏中间件覆盖密钥与 token 模式
5. [ ] 管理员接口（credential/profile/rotate/disable）

### 10.3 前端层

1. [ ] `New Run` 改为 profile 下拉
2. [ ] 删除 `api_key/base_url` 明文输入组件
3. [ ] Run Detail 展示 `profile_name/profile_id`
4. [ ] 错误提示改为 profile 失效/权限不足语义

### 10.4 治理与发布

1. [ ] RBAC 权限矩阵（admin/operator/viewer）
2. [ ] 审计字段落库与查询接口
3. [ ] 凭据轮换演练（灰度 + 回滚）
4. [ ] 上线前安全检查（日志抽样 + DB 抽样）
