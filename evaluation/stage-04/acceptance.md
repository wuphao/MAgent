# 阶段 04 验收记录

- 阶段与提交版本：阶段 04，工作区未提交。
- 环境、依赖锁定版本、是否真实模型/GPU：Python 3.11.0；Pydantic 2.11.9；openpyxl 3.1.5；pytest 9.1.1 从 `evaluation/stage-01/test-packages/` 临时加入 `sys.path`。本阶段未调用 LLM，未启用 DiaMond/GPU。
- 场景 ID、输入指纹、配置/规则/提示词版本：覆盖 S10、S11、S12、S13，并回归 S01、S03、S04、S07、S08；能力版本 `xx_v1_score/1`、`longitudinal_describe/1`；领域定义 `xx-v1:1`。
- 实际执行命令：
  - `python -c "import sys; sys.path[:0]=['evaluation/stage-01/test-packages','src']; import pytest; raise SystemExit(pytest.main(['tests/unit/test_contracts.py','tests/integration/test_storage.py','tests/integration/test_schema_variants.py','tests/integration/test_mapping_validation.py','tests/integration/test_semantic_mapping.py','tests/integration/test_metadata_resume.py','tests/integration/test_specialists.py','tests/acceptance/test_semantic_analysis.py','-q']))"`
  - `python -m compileall src tests evaluation\compare_runs.py main.py`
  - `python -c "import sys, runpy; sys.path.insert(0,'src'); sys.argv=['adapt','tests/fixtures/schema_variants/xx_v1_legacy_rwe.json','--mapping','configs/mappings/xx_v1_legacy_json.json','--project-id','stage04','--source-namespace','legacy-json','--data-dir','evaluation/stage-04/v2-store-verified','--output','evaluation/stage-04/adaptation_legacy_json.json']; runpy.run_module('multi_agent.application.adapt_cli', run_name='__main__')"`
  - `python -c "import sys, runpy; sys.path.insert(0,'src'); sys.argv=['specialist','--db','evaluation/stage-04/v2-store-verified/stage02.sqlite3','--project-id','stage04','--goal','xx_v1_assessment','--output','evaluation/stage-04/specialist_results_legacy_json.json']; runpy.run_module('multi_agent.application.specialist_cli', run_name='__main__')"`
  - `rg -n "raw_case|normalized_case|moca|mmse|faq|cdr|adas|patient_number|visit_date|record_id|总分|量表" src\multi_agent\agents src\multi_agent\capabilities`
- 通过、失败、跳过数量及原因：32 个 pytest 用例通过。`rg` 检查无命中，说明新 Agent/Capability 未读取旧 memory 或来源字段名；概念名 `xx_v1.total` 属于标准语义概念，不是源字段依赖。
- 确定性结果及引用检查：`AssessmentAgent` 对 2024-01-01 重算总分 4，对 2024-07-01 重算总分 6，均与报告分一致；每条 finding 包含支持它的 ObservationRef 和 ToolArtifact 引用。`LongitudinalAgent` 输出总分从 4 到 6，delta 为 2，标注两点只能做描述性变化。
- 规则核查表：见 `evaluation/stage-04/rule-audit.md`。FAQ 备注类字段通过阶段 02 未映射字段和阶段 04 计分测试验证，不进入条目求和。
- 工具契约：见 `evaluation/stage-04/capability-contracts.md`。demo/unavailable 能力不会进入正式 invoker 选择。
- 各专业结果：见 `evaluation/stage-04/specialist_results_legacy_json.json` 和 `evaluation/stage-04/specialist_results_csv_long.json`。
- 旧新差异解释：见 `evaluation/stage-04/differences.md`。未知旧字段不再要求改专业 Agent；字段适配由阶段 02 完成。
- 费用、耗时、资源记录：本阶段未调用 LLM；最终 pytest 用例 1.73 秒；未启动 DiaMond/GPU。
- 待解决问题、是否满足出口：阶段 04 工程出口满足。MMSE/MoCA/FAQ/CDR/ADAS 的 active 规则登记和逐项迁移尚未完成，原因是缺少本轮验证用的独立规则来源；当前没有从旧 Agent 硬编码反推为已确认定义。
- 回退点与数据备份位置：停用 stage04 specialist CLI 或对应 capability version 即可回退；旧系统仍通过 `main.py --engine legacy` 独立运行。已发布 v2 证据不交给旧 `synthesis_agent` 拼接。
