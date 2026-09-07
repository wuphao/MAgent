# 阶段 08 影子运行与切换报告

## 切换结论

默认 CLI 入口已切到 v2，旧流程通过 `--engine legacy` 保留。此次切换范围是本地模块化单体：CLI/API + SQLite + 本地资产仓 + 单机工作进程。

真实 DiaMond 推理未纳入默认完成能力；它仍需外部真实输入、权重和运行环境验证。切换不删除旧模块。

## 影子运行样例

v2 样例使用 `tests/fixtures/stage06/xx_v1_scoring_conflict.csv`，输出为 `evaluation/stage-08/main_v2_run.json`。

该样例展示：

- 陌生 CSV 布局通过 mapping 接入。
- 观测和 evidence 以稳定 id 存储。
- AssessmentAgent 发现 2024-01-01 报告总分 0 与条目重算 4 冲突。
- Critic/Review 形成 unresolved challenge，不任意替换来源值。
- ReportSnapshot 发布 `completed_with_limitations`。

## 与 legacy 的关系

legacy 入口继续支持原患者 JSON 和旧 Agent 输出格式。legacy 输出不是 v2 金标准；差异按事实覆盖、规则适用性、限制表达和来源追溯分类。由于当前 stage08 样例是新 CSV fixture，未与 legacy 单患者 JSON 做一对一事实比较。

## 未交付能力

- 真实 DiaMond 模型推理。
- HTTP FastAPI 服务包装。
- 多机共享数据库/对象仓/队列部署。
- OCR、向量检索、跨运行自动规则激活。
