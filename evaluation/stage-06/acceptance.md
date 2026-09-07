# 阶段 06 验收：综合、质询、定向复核与发布

## 实现范围

阶段 06 将阶段 05 的 `summary_placeholder` 替换为可执行的 `SynthesisAgent`，形成第一次完整协作闭环：专业 Agent 发现 → 证据目录 → 确定性质询 → 定向复核 → 报告快照 → JSON/Markdown/TXT 三格式发布。

本阶段新增协议与模块：

- `domain/challenges.py`：Challenge、ReviewTask、ReviewOutcome。
- `domain/reports.py`：ReportSnapshot、ReportCoverage。
- `collaboration/synthesis.py`：任务结果与工具产物目录，不截断超过 20 条发现。
- `collaboration/conflict_rules.py`、`critic.py`：计分冲突与引用错误规则审查。
- `collaboration/review_policy.py`、`review_router.py`、`termination.py`：复核选择、路由与终止策略。
- `reporting/publisher.py`、`validators.py`、`renderers.py`、`snapshot.py`：发布门禁与三格式渲染。
- `agents/synthesis.py`：接入阶段 05 调度器。

## 验收命令

```powershell
python -c "import sys; sys.path[:0]=['evaluation/stage-01/test-packages','src']; import pytest; raise SystemExit(pytest.main(['tests/acceptance/test_review_loop.py','tests/acceptance/test_report_publication.py','-q']))"
python -c "import sys; sys.path[:0]=['evaluation/stage-01/test-packages','src']; import pytest; raise SystemExit(pytest.main(['tests/unit','tests/integration','tests/acceptance','-q']))"
python -m compileall src tests evaluation\compare_runs.py main.py
```

结果：

- 阶段 06 验收：5 passed。
- 全量测试：49 passed in 3.75s。
- 编译检查通过。

## 冲突闭环样例

输入文件：`tests/fixtures/stage06/xx_v1_scoring_conflict.csv`。

关键冲突：2024-01-01 同一记录中，四个条目重算总分为 4，但来源 `xx_v1.total` 为 0。

系统行为：

1. `AssessmentAgent` 生成 unresolved finding：computed total 4 differs from reported total 0。
2. `CriticAgent` 生成 scoring challenge，要求复核计分定义、条目完整性和 total 字段语义。
3. `ReviewRouter` 在没有字段定义修订或人工回查材料时，输出 unresolved outcome。
4. `ReportPublisher` 发布 `completed_with_limitations`，保留两个值，不任意替换。

## 报告产物

- `evaluation/stage-06/run_with_review.json`：完整调度轨迹。
- `evaluation/stage-06/challenge_trace.json`：质询、复核和发现修订链。
- `evaluation/stage-06/report_snapshot.json`：发布快照。
- `evaluation/stage-06/report.json`：JSON 渲染。
- `evaluation/stage-06/report.md`：Markdown 渲染。
- `evaluation/stage-06/report.txt`：TXT 渲染。

旧报告入口的 v2 分支也已验证：

- `generate_explainable_report.py --v2-report-snapshot` 从同一 `ReportSnapshot` 渲染 Markdown。
- `generate_agent_text_report.py` 识别 `stage06.report_snapshot/1` 后直接渲染 TXT，不再调用模型重新推断。

## 边界说明

阶段 06 的复核策略是配置优先级与确定性规则，不声称训练出最优策略。当前能处理计分冲突、引用错误和缺证据协议约束；解释性遗漏的 LLM 反证只预留协议入口，未作为已验证能力发布。映射修订后的跨运行增量恢复留到阶段 08。

