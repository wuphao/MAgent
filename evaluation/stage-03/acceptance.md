# 阶段 03 验收记录

- 阶段与提交版本：阶段 03，工作区未提交。
- 环境、依赖锁定版本、是否真实模型/GPU：Python 3.11.0；Pydantic 2.11.9；openpyxl 3.1.5；pytest 9.1.1 从 `evaluation/stage-01/test-packages/` 临时加入 `sys.path`。本阶段未调用真实 LLM，候选生成验收使用 `FakeModelGateway`；未启用 DiaMond/GPU。
- 场景 ID、输入指纹、配置/规则/提示词版本：覆盖 S05、S06、S09，并回归 S01、S03、S04、S07、S08；候选提示词版本 `stage03-mapping-candidate/1`；激活策略 `stage03-default`；领域定义 `xx-v1:1`。
- 实际执行命令：
  - `python -c "import sys; sys.path[:0]=['evaluation/stage-01/test-packages','src']; import pytest; raise SystemExit(pytest.main(['tests/unit/test_contracts.py','tests/integration/test_storage.py','tests/integration/test_schema_variants.py','tests/integration/test_mapping_validation.py','tests/integration/test_semantic_mapping.py','tests/integration/test_metadata_resume.py','-q']))"`
  - `python -m compileall src tests evaluation\compare_runs.py main.py`
  - `python -c "import sys, runpy; sys.path.insert(0,'src'); sys.argv=['metadata','questions','tests/fixtures/stage03/metadata_questions.json']; runpy.run_module('multi_agent.application.metadata_service', run_name='__main__')"`
  - `python -c "import sys, runpy; sys.path.insert(0,'src'); sys.argv=['metadata','--store','evaluation/stage-03/metadata_revisions.json','submit','--question-id','q_score_type','--answer','score is raw total for XX-v1 version 1','--source','tests/fixtures/schema_variants/expected.json','--idempotency-key','stage03-metadata-1']; runpy.run_module('multi_agent.application.metadata_service', run_name='__main__')"`
- 通过、失败、跳过数量及原因：24 个 pytest 用例通过。真实模型候选效果未验收，原因是本阶段只建立网关与 fake 验收；真实模型效果和成本需单独记录，不能用 fake 结果替代。
- 确定性结果及引用检查：`MappingCandidateAgent` 只接收注册概念和白名单算子；未知算子、未知概念、非法候选无法激活。源数据中的 instruction-like 文本被作为数据处理，产生元数据问题，不执行。
- 映射候选及字段依据：见 `evaluation/stage-03/candidate_validated.json`。confidence 只保存为诊断信息，不能触发自动激活。
- 验证报告：见 `evaluation/stage-03/validation_report.json`。结构验证和语义验证分开保存；语义审查不能覆盖结构失败。
- active/needs_metadata 比例：fake 验收样例中 1 个候选进入 active，1 个候选进入 needs_metadata，非法候选进入 rejected/invalid。
- 漂移与复用：同一列结构但单位从 `points` 变为 `percent` 时，`decide_reuse` 返回 `suspend_active_mapping`，不能仅凭列名复用。
- 补说明前后快照：见 `evaluation/stage-03/metadata_resume.md` 与 `evaluation/stage-03/metadata_revisions.json`。同一 `idempotency_key` 重复提交返回同一修订。
- 费用、耗时、资源记录：本阶段未调用 LLM；最终 pytest 用例 1.13 秒；未启动 DiaMond/GPU。
- 待解决问题、是否满足出口：阶段 03 工程出口满足。真实模型保留布局集效果、调用成本、错误自动发布率尚未实测；这属于后续接入真实模型时的验收项。
- 回退点与数据备份位置：禁用 `MappingCandidateAgent` 或不调用候选生成功能即可回退；阶段 02 的人工映射仍可用；已验证人工映射不会因候选机制降低激活标准。
