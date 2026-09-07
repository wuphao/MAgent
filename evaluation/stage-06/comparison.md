# 阶段 06 协作对照

| 方案 | 行为 | 风险 | 阶段 06 结果 |
|---|---|---|---|
| 单 Agent 总结 | 直接把所有 Agent 输出拼成一段报告 | 容易把冲突写成结论，引用和限制丢失 | 不采用；报告从 ReportSnapshot 渲染 |
| 固定流水线 | assessment → longitudinal → summary | 能跑通，但 summary 不知道哪里需要复核 | 保留任务 DAG，并新增 SynthesisAgent 读取上游结构化结果 |
| 多角色投票 | 多个 Agent 给出意见后取多数 | 共享同一来源时会虚增证据强度 | EvidenceCatalog 保留共享祖先引用，不把重复引用当独立证据 |
| 定向复核 | 对具体发现生成 Challenge，再按能力复核 | 需要额外协议和终止条件 | 已实现 scoring/reference 规则、ReviewTask、ReviewOutcome |

## 成本与错误变化

| 指标 | 阶段 05 | 阶段 06 |
|---|---:|---:|
| `multi_source_summary` 可执行任务 | 6 个，其中 summary 为占位 | 6 个，其中 synthesis_report 真实执行 |
| LLM 调用 | 0 | 0 |
| 预算流水 | 每任务 settle 一条 | 每任务 settle 一条，synthesis 也记录 |
| 能发现的新增错误 | 调度、依赖、预算错误 | 计分冲突、引用错误、缺证据协议错误 |
| 报告状态 | success 运行结果 | completed / completed_with_limitations / failed 快照状态 |

新增错误被单列到 `challenges` 与 `review_outcomes`，不并入“已解决问题”统计。未决复核会进入 `limitations`，不会被 Markdown 或 TXT 渲染改写为已完成审查。
