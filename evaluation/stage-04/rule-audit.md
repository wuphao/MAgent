# 阶段 04 规则核查表

## XX-v1

- 定义来源：`configs/instruments/xx-v1.json`
- 状态：`active`
- 已登记条目：`xx_v1.item_1`、`xx_v1.item_2`、`xx_v1.item_3`、`xx_v1.item_4`
- 已登记总分：`xx_v1.total`
- 计分规则：四个条目求和；任一条目缺失时不计算总分。
- 分数方向：`higher_is_more`
- 报告分处理：保留为来源 Observation；重算分作为 ToolArtifact；二者不一致时生成 unresolved finding。
- 备注字段处理：`remark` 只出现在阶段 02 的未映射字段报告，不进入计分。

## 未迁移实际量表

MMSE、MoCA、FAQ、CDR、ADAS 尚未在本阶段登记为 active 规则。旧代码中的字段名和阈值没有被反推为已确认规则；后续需要逐项补来源、版本、条目角色、缺项规则和解释依据。
