# 阶段 05 调用账本

本阶段的演示任务全部是本地确定性能力，因此账本中 `calls=0`、`tokens=0`、`cost=null` 是对“无模型调用”的记录，不代表未知费用被写成 0。

预算测试覆盖：

- 调用次数与 token 预留超过硬限制时拒绝派发。
- 结算允许 `usage_unknown=1`，用于表示请求可能已被供应商接受但响应丢失。
- `FakeModelGateway` 可携带 `BudgetContext(run_id, task_id, reserved_tokens, prompt_version)`，并能模拟 timeout。

真实模型费用、token 与错误码适配仍属于后续真实模型验证项。
