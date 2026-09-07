# 阶段 08 验收：恢复、增量、API 与默认切换

## 实现范围

阶段 08 将前七阶段的 v2 闭环加固为可恢复、可查询、可局部重算和可默认使用的本地交付形态。

新增模块：

- `storage/leases.py`：任务租约、attempt_id、fencing_token，防止租约过期后的晚到结果覆盖新结果。
- `storage/outbox.py`：outbox 事件表与 event_id 去重。
- `storage/dependencies.py`：版本化依赖边与影响闭包。
- `orchestration/recovery.py`：过期租约恢复、staging 产物修复、outbox pending 状态检查。
- `orchestration/incremental.py`：根据修订引用生成受影响任务集合。
- `application/api.py`：纯 Python API service，覆盖 dataset profile、analysis run、cancel、report、challenges、evidence 查询。

交付切换：

- `main.py` 默认 engine 已切为 `v2`。
- `--engine legacy` 保留旧流程兼容入口。
- `main.py` 新增 `--mapping`、`--v2-goal`、`--task-db`、`--parallel`。
- README 已更新为 v2 默认流程。

## 验收命令

```powershell
python -c "import sys; sys.path[:0]=['evaluation/stage-01/test-packages','src']; import pytest; raise SystemExit(pytest.main(['tests/acceptance','-q']))"
python -c "import sys; sys.path[:0]=['evaluation/stage-01/test-packages','src']; import pytest; raise SystemExit(pytest.main(['tests/integration/test_recovery.py','tests/integration/test_api_scope.py','-q']))"
python -c "import sys; sys.path[:0]=['evaluation/stage-01/test-packages','src']; import pytest; raise SystemExit(pytest.main(['tests/unit','tests/integration','tests/acceptance','-q']))"
python -m compileall src tests evaluation\compare_runs.py main.py explainable_report.py generate_explainable_report.py generate_agent_text_report.py
```

## 验收结果

- acceptance：9 passed, 1 skipped in 0.72s。
- recovery/API 集成：10 passed in 1.60s。
- 全量测试：65 passed, 1 skipped in 5.01s。
- 编译检查通过。
- 敏感词扫描仅命中正常业务错误码 BUDGET_TOKENS_EXCEEDED。

## 已覆盖场景

- 过期租约被重新领取，旧 fencing token 的晚到结果不能覆盖新结果。
- 恢复器将过期 running 任务重排为 ready。
- outbox 同一 event_id 重复入队被去重。
- staging 产物按内容 hash 修复到不可变对象路径。
- mapping 修订影响闭包只生成 assessment、longitudinal、synthesis 分支，不重跑无关影像。
- API 项目越权返回 not_found，避免泄露对象存在性。
- API 同 idempotency_key 不同请求体返回 `IDEMPOTENCY_CONFLICT`。
- API 创建分析运行后可查询 report、challenges 和受项目/主体作用域保护的 evidence。
- API 查询或取消 run 时会再次检查 run_id 与 project_id 的仓储归属，避免跨项目 run_id 混淆。
- 重复 create_run 不会清空已有任务状态和结果。
- 默认 CLI v2 可从 CSV + mapping 跑到 `multi_source_summary`。

## 产物

- `evaluation/stage-08/main_v2_run.json`：默认 v2 CLI 样例。
- `evaluation/stage-08/shadow-cutover.md`：影子运行与默认切换说明。
- `configs/deployment/local.example.json`：本地部署配置示例。
- `docs/运行与恢复/本地部署与恢复手册.md`：安装、运行、恢复、备份、回滚说明。
- `docs/运行与恢复/能力可用清单.md`：能力状态与边界。

## 边界

阶段 08 仍保持模块化单体，不引入 HTTP 框架，不启用多机共享队列。真实 DiaMond 推理、OCR、向量检索、跨运行自动规则激活仍标为未交付或外部条件未满足。



