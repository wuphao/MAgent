# 阶段 01 基线记录

## 环境与依赖

- Python：3.11.0
- Pydantic：2.11.9
- pytest：当前环境未安装，已在 `pyproject.toml` 的 `dev` 额外依赖中声明。
- LLM：旧入口只有 `--use-llm` 才实际调用 DeepSeek；阶段 01 验收不启用。
- GPU/DiaMond：本阶段合成夹具不包含影像路径，旧影像 Agent 不应启动 DiaMond；未把 GPU 可用性作为阶段 01 成功条件。

## 输入清单

- `tests/fixtures/stage01/xx_v1_legacy_case.json`：脱敏合成旧格式 JSON，主体为 `S001`，包含虚构 `XX-v1` 两次测评与空 `imaging`。
- `tests/fixtures/stage01/expected.json`：独立手写期望，XX-v1 两次总分分别为 4、6，差值为 2。

## 旧行为摘要

旧流程入口为 `main.py`，默认 `legacy`，读取 JSON 后经 `case_memory.init_case_memory` 创建可变字典，再由 `Orchestrator` 串行运行各旧 Agent。

阶段 01 保留旧流程作为回退入口。由于合成夹具的 `XX-v1` 不属于旧 Agent 的固定表单，旧 Agent 不应产生针对 XX-v1 的专业结论；这个差异属于预期能力缺失，不作为新协议错误。

## 新行为基线

v2 阶段 01 只登记来源资产、发布顶层数据盘点观测、冻结快照，并明确返回 `clinical_analysis` 的 `capability_unavailable`。不得把该结果包装成完整临床报告。
