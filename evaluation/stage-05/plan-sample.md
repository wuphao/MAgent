# 阶段 05 目标计划样例

目标：`multi_source_summary`

计划由模板规划器生成，不依赖 LLM 自由规划。当前展开为：

| task_id | 执行方 | 依赖 | required | 说明 |
|---|---|---|---|---|
| `quality_xx_v1` | `QualityService` | 无 | 是 | 检查 XX-v1 量表分析所需 Observation 是否存在。 |
| `assessment_xx_v1` | `AssessmentAgent` / `xx_v1_score` | `quality_xx_v1` required_success | 是 | 重算 XX-v1 总分并核对报告分。 |
| `quality_longitudinal` | `QualityService` | 无 | 是 | 检查纵向分析所需 `xx_v1.total` 是否存在。 |
| `longitudinal_xx_v1` | `LongitudinalAgent` / `longitudinal_describe` | `quality_longitudinal` required_success | 是 | 计算同一主体同一概念的描述性变化。 |
| `laboratory_optional` | `LaboratoryGeneticsAgent` | 无 | 否 | 无实验室/遗传数据时作为覆盖信息保留，不阻断主目标。 |
| `summary_placeholder` | none | 三个专业任务 terminal | 否 | 第六阶段综合报告占位，不宣称反证闭环。 |

`plan_only.json` 保存了完整 `AnalysisRequest`、`Plan` 和 `PlanValidationResult`。
