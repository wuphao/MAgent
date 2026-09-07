# 阶段 05 状态迁移记录

状态机允许：

- `pending -> ready -> running -> succeeded`
- `running -> retry_wait -> ready`
- `running -> failed`
- `pending -> needs_metadata`
- `pending/ready -> skipped`

本阶段使用 `TaskStore.transition(run_id, task_id, expected, new)` 做预期状态条件更新。非法迁移会抛出错误，避免任务被重复提交或从错误状态跳转。

串行和并行演示在同一输入上得到相同终态：

```text
assessment_xx_v1: succeeded
laboratory_optional: succeeded
longitudinal_xx_v1: succeeded
quality_longitudinal: succeeded
quality_xx_v1: succeeded
summary_placeholder: succeeded
```

`summary_placeholder` 的 result 为 `{"status": "skipped", "reason": "skipped_until_stage06"}`，表示第六阶段前不生成综合报告。
