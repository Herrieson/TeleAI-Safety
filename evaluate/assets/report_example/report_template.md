# 报告标题：[[REPORT_TITLE]]

## 执行摘要
[[EXEC_SUMMARY]]

## 第1章：评测资产定义与测试环境
本章用于定义评测边界、资产清单与测试环境，保证报告可复现。

### 1.1 被测资产清单
[[ASSET_INTRO]]

[[ASSET_TABLE]]

### 1.2 关键评测域与攻击面映射
[[EVAL_SCOPE_TEXT]]

- 覆盖攻击向量：[[ATTACK_SET_LIST]]
- 核心指标体系：[[CORE_METRICS_LIST]]

### 1.3 测试环境拓扑与配置
[[ENV_TEXT]]

[[ENV_TABLE]]

### 1.4 测试工具链与方法论
[[METHODOLOGY_TEXT]]

## 第2章：核心安全态势与风险量化

### 2.1 基础攻防双维指标：ASR 与 FRR
[[ASR_FRR_DEF_BLOCK]]

[[BASE_METRIC_VALUES]]

[[BASE_DIAGNOSIS]]

### 2.2 细粒度防御分布指标
[[ATTACK_METRIC_DEF_BLOCK]]

[[ATTACK_TABLE]]

[[ATTACK_DIAGNOSIS]]

### 2.3 进阶风险评估（MDS / Kappa / Bias / WSL / CM）
[[ADV_METRIC_DEF_BLOCK]]

[[ADV_METRIC_VALUES]]

[[ADV_DIAGNOSIS]]

## 第3章：横向对标——专项防御能力分析
[[FOCUS_COMPARE_INTRO]]

[[FOCUS_COMPARE_TABLE]]

[[FOCUS_LINES]]

[[INSIGHT_LINES]]

## 第4章：纵向诊断——模型自身特性分析
[[VERTICAL_DIAGNOSIS]]

## 第5章：典型案例复盘
[[CASE_REVIEW_BLOCK]]

## 第6章：改进建议与路线图
[[RECOMMENDATION_LINES]]

### 6.1 短期（1-2个迭代）
- 优先针对前两类高风险攻击向量建立发布门禁与回归集。

### 6.2 中期（季度）
- 结合失败样本做对齐数据补强，优化拒答边界并降低误拒。

### 6.3 长期（年度）
- 形成模型内生防御、网关审查、人审复核的三层合规架构。

## 第7章：可视化仪表盘
### 7.1 综合热力图
[[HEATMAP_BLOCK]]

### 7.2 排行图与风险面板
[[PLOT_PANEL_BLOCK]]

## 第8章：审校与一致性检查
[[AUDIT_LINES]]

## 附录A：模型全指标画像
[[MODEL_TABLE]]

## 附录B：攻击向量画像
[[ATTACK_TABLE_ALL]]

## 附录C：证据索引
[[EVIDENCE_TABLE]]

## 附录D：指标定义（来自 metrics catalog）
[[METRICS_APPENDIX]]

## 附录E：ASR 综合矩阵
[[SUMMARY_TABLE]]
