# 阶段 01 验收记录

- 阶段与提交版本：阶段 01，工作区未提交。
- 环境、依赖锁定版本、是否真实模型/GPU：Python 3.11.0；Pydantic 2.11.9；pytest 9.1.1 与 wheel 0.48.0 下载到 `evaluation/stage-01/test-packages/` 后临时加入 `sys.path` 执行；本阶段未启用真实 LLM/GPU。
- 场景 ID、输入指纹、配置/规则/提示词版本：S03；输入为 `tests/fixtures/stage01/xx_v1_legacy_case.json`；SHA-256 为 `3e833e2b679fadf132fd61b1aa65952a9307c01f6c0d78d95ef5a6e7d3bafb50`；解析器 `stage01-json-inventory/1`；映射 `stage01-inventory/1`。
- 实际执行命令：
  - `python main.py --engine legacy tests\fixtures\stage01\xx_v1_legacy_case.json --full --output evaluation\stage-01\legacy_full.json`
  - `python main.py --engine v2 tests\fixtures\stage01\xx_v1_legacy_case.json --project-id stage01 --source-namespace synthetic --data-dir evaluation\stage-01\v2-store-verified --output evaluation\stage-01\v2_inventory_first_verified.json`
  - `python main.py --engine v2 tests\fixtures\stage01\xx_v1_legacy_case.json --project-id stage01 --source-namespace synthetic --data-dir evaluation\stage-01\v2-store-verified --output evaluation\stage-01\v2_inventory_second_verified.json`
  - `python -c "import sys; sys.path[:0]=['evaluation/stage-01/test-packages','src']; import pytest; raise SystemExit(pytest.main(['tests/unit/test_contracts.py','tests/integration/test_storage.py']))"`
  - `python -c "import sys, runpy; sys.path.insert(0, 'src'); sys.argv=['python -m multi_agent.application.cli','--help']; runpy.run_module('multi_agent.application.cli', run_name='__main__')"`
  - `python evaluation\compare_runs.py evaluation\stage-01\v2_inventory_first_verified.json evaluation\stage-01\v2_inventory_second_verified.json`
- 通过、失败、跳过数量及原因：8 个 pytest 用例通过；旧入口合成输入运行成功；v2 首次运行插入 4 条观测和 1 条 evidence；v2 第二次运行复用 4 条观测和 1 条 evidence。
- 确定性结果及引用检查：重启后从 `evaluation/stage-01/v2-store-verified/stage01.sqlite3` 读取到 4 条 `stage01` 观测；示例观测保留 `$.imaging` 与 `$.imaging.__count__` 来源定位。快照 `snapshot_e472b5d6fc3e595344b4` 固定 4 个成员引用。
- 与旧版本差异及分类：XX-v1 不属于旧固定表单，旧入口报告缺少 moca/mmse/faq/cdr/adas 并等待影像路径，差异分类为能力缺失或预期纠错，不能用自然语言一致性判定正确。v2 只做来源盘点并明确 `clinical_analysis` 为 `capability_unavailable`。
- 费用、耗时、资源记录：本阶段未调用 LLM；最终 pytest 用例 0.27 秒；未启动 DiaMond/GPU。
- 待解决问题、是否满足出口：阶段 01 出口满足。当前机器全局缺少 pytest、wheel，且用户 site-packages 不可写；已使用项目内测试依赖目录完成验收。若要严格执行裸命令 `python -m multi_agent.application.cli --help`，需要先安装项目包或设置 `PYTHONPATH=src`。
- 回退点与数据备份位置：使用 `python main.py --engine legacy ...` 回退；v2 默认数据目录为 `data/v2/`，本次验收运行库在 `evaluation/stage-01/v2-store-verified/`，该运行库可再生成。
