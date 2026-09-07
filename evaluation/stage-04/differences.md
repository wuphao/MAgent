# 阶段 04 旧新差异解释

- 旧 Agent 从 `raw_case` / `normalized_case` 读取固定字段；新 Agent 只接收标准 Observation。
- 旧流程遇到未知 `xx_v1` 字段不会形成专业量表结论；新流程通过阶段 02 映射后，可以对 `xx_v1` 执行已登记规则。
- 新 AssessmentAgent 保留报告分与重算分差异，不覆盖来源总分。
- 新 LongitudinalAgent 在缺日期、同日或时间精度不足时返回不足状态，不用“未见明确下降”替代无效分析。
- 新 QualityService 按目标检查数据覆盖。只请求 `xx_v1_assessment` 或 `longitudinal_xx_v1` 时，缺影像不使任务失败。

这些差异属于预期纠错：新结果按独立 XX-v1 定义和阶段 02 语义观测计算，不以旧自然语言结论一致为正确性标准。
