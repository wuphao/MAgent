# 阶段 05 验收记录

- 阶段与提交版本：阶段 05，工作区未提交。
- 环境、依赖锁定版本、是否真实模型/GPU：Python 3.11.0；Pydantic 2.11.9；openpyxl 3.1.5；pytest 9.1.1 从 `evaluation/stage-01/test-packages/` 临时加入 `sys.path`。本阶段未调用真实 LLM，未启用 DiaMond/GPU。
- 场景 ID、输入指纹、配置/规则/提示词版本：覆盖 S13、S14、S15，并回归 S01、S03、S04、S07、S08、S10-S12；能力版本 `xx_v1_score/1`、`longitudinal_describe/1`；调度模板为阶段 05 显式模板。
- 实际执行命令：
  - `python -c "import sys; sys.path[:0]=['evaluation/stage-01/test-packages','src']; import pytest; raise SystemExit(pytest.main(['tests/unit/test_contracts.py','tests/integration/test_storage.py','tests/integration/test_schema_variants.py','tests/integration/test_mapping_validation.py','tests/integration/test_semantic_mapping.py','tests/integration/test_metadata_resume.py','tests/integration/test_specialists.py','tests/acceptance/test_semantic_analysis.py','tests/integration/test_scheduler.py','tests/integration/test_model_budget.py','-q']))"`
  - `python -m compileall src tests evaluation\compare_runs.py main.py`
  - `python -c "import sys, runpy; sys.path.insert(0,'src'); sys.argv=['run','--evidence-db','evaluation/stage-04/v2-store-verified/stage02.sqlite3','--task-db','evaluation/stage-05/tasks-plan.sqlite3','--project-id','stage04','--goal','multi_source_summary','--plan-only','--output','evaluation/stage-05/plan_only.json']; runpy.run_module('multi_agent.application.run_cli', run_name='__main__')"`
  - `python -c "import sys, runpy; sys.path.insert(0,'src'); sys.argv=['run','--evidence-db','evaluation/stage-04/v2-store-verified/stage02.sqlite3','--task-db','evaluation/stage-05/tasks-serial.sqlite3','--project-id','stage04','--goal','multi_source_summary','--output','evaluation/stage-05/run_serial.json']; runpy.run_module('multi_agent.application.run_cli', run_name='__main__')"`
  - `python -c "import sys, runpy; sys.path.insert(0,'src'); sys.argv=['run','--evidence-db','evaluation/stage-04/v2-store-verified/stage02.sqlite3','--task-db','evaluation/stage-05/tasks-parallel.sqlite3','--project-id','stage04','--goal','multi_source_summary','--parallel','--output','evaluation/stage-05/run_parallel.json']; runpy.run_module('multi_agent.application.run_cli', run_name='__main__')"`
- 通过、失败、跳过数量及原因：44 个 pytest 用例通过。非法计划测试返回 `invalid_plan` 且 `executed=0`。必需数据缺失时质量任务 failed，依赖任务 skipped。取消请求下不派发新任务。
- 目标计划样例：见 `evaluation/stage-05/plan-sample.md` 与 `evaluation/stage-05/plan_only.json`。
- 状态迁移记录：见 `evaluation/stage-05/state-transitions.md`。重试从 `running -> retry_wait -> ready`，最多执行配置的 `max_attempts`。
- 调用账本：见 `evaluation/stage-05/budget-ledger.md`。本地确定性任务无模型调用；预算测试覆盖硬限制、usage_unknown 和 fake timeout。
- 串并行对照：见 `evaluation/stage-05/serial-parallel-compare.md`。串行和并行任务终态一致；Artifact ID 由于含执行时间戳，不要求逐字一致。
- 可选任务失败/缺数据：`laboratory_optional` 在无 lab/genetic Observation 时返回 `no_data`，因为它是可选任务，作为覆盖信息保留，不阻断综合占位任务。
- 费用、耗时、资源记录：本阶段未调用 LLM；最终全量 pytest 用例 3.36 秒；未启动 DiaMond/GPU。
- 待解决问题、是否满足出口：阶段 05 工程出口满足。自由规划协调 Agent 尚未启用；真实模型网关的供应商错误码、真实 token/cost 统计留到后续真实模型验证。
- 回退点与数据备份位置：可回退到阶段 04 的 `specialist_cli` 固定顺序驱动；调度任务库 `evaluation/stage-05/tasks-*.sqlite3` 为可再生成运行物，已加入 `.gitignore`。
