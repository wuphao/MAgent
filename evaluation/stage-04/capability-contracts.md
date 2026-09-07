# 阶段 04 工具契约

| capability_id | version | 输入 | 输出 | availability | 说明 |
|---|---|---|---|---|---|
| `xx_v1_score` | `xx_v1_score/1` | `Observation[xx_v1.item_1..item_4]` 与可选 `xx_v1.total` | `ToolArtifact[xx_v1.computed_total]` | `active` | 只按 `InstrumentSpec` 注册条目重算，报告分只用于核对，不覆盖来源值。 |
| `longitudinal_describe` | `longitudinal_describe/1` | 同一主体、同一概念、同一 mapping revision、同一单位的数值日期序列 | `ToolArtifact[trajectory_summary]` | `active` | 先排序并检查不同日期；两点只输出描述性变化。 |

`CapabilityInvoker` 统一返回 `success`、`unavailable`、`not_applicable`、`technical_failure`。执行前再次检查 capability 是否注册且为 `active`；`demo` 能力不会被正式选择。
