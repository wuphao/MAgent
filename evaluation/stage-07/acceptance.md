# 阶段 07 验收：文本、知识与影像接入

## 实现范围

阶段 07 在阶段 01—06 的协议和任务接口上补齐新数据类型，不新建另一套编排系统。

新增模块：

- `ingestion/parsers/text.py`：txt/md/PDF 可提取文字解析，保留页码、段落和字符区间。
- `capabilities/text_validation.py`：片段定位校验与文本观测抽取，区分否定、家属史、未来计划。
- `knowledge/documents.py`、`index.py`、`retrieval.py`、`rules.py`：版本化知识文档、精确检索和规则候选。
- `agents/knowledge.py`：返回带出处片段的规则候选，不直接激活评分规则。
- `capabilities/imaging/*`：影像资产检查、DiaMond 兼容性验证、预处理入口和拒绝路径。
- `agents/imaging.py`：只执行兼容性验证；条件不足时返回能力不可用。

新增能力配置：

- `configs/capabilities/text_extract.json`
- `configs/capabilities/knowledge_retrieve.json`
- `configs/capabilities/diamond_validate.json`

新增目标：`multimodal_summary`。计划器会把 `text_observations`、`knowledge_candidates`、`diamond_compatibility` 作为可选模态任务加入 DAG，并让 `synthesis_report` 等待它们进入终态。

## 验收命令

```powershell
python -c "import sys; sys.path[:0]=['evaluation/stage-01/test-packages','src']; import pytest; raise SystemExit(pytest.main(['tests/integration/test_text_knowledge.py','tests/integration/test_imaging_contract.py','-q']))"
python -c "import sys; sys.path[:0]=['evaluation/stage-01/test-packages','src']; import pytest; raise SystemExit(pytest.main(['-m','real_imaging','tests/acceptance/test_imaging_runtime.py','-q']))"
python -c "import sys; sys.path[:0]=['evaluation/stage-01/test-packages','src']; import pytest; raise SystemExit(pytest.main(['tests/unit','tests/integration','tests/acceptance','-q']))"
python -m compileall src tests evaluation\compare_runs.py main.py explainable_report.py generate_explainable_report.py generate_agent_text_report.py
```

结果：

- 文本/知识/影像契约测试：6 passed。
- 真实影像 runtime：1 skipped，原因是未提供真实 MRI/PET、checkpoint hash 和完整运行环境。
- 全量测试：55 passed, 1 skipped in 4.13s。
- 编译检查通过。

## 产物

- `evaluation/stage-07/text_extraction.json`：文本段落、定位和抽取观测对照。
- `evaluation/stage-07/knowledge_retrieval.json`：检索命中、版本化出处和规则候选。
- `evaluation/stage-07/imaging_contract.json`：影像拒绝路径、兼容探针和缓存键失效验证。
- `evaluation/stage-07/multimodal_plan.json`：第七阶段目标 DAG 样例。
- `evaluation/stage-07/imaging-compatibility.md`：DiaMond 真实运行要求核查。

## 边界

PDF OCR 未实现；扫描 PDF 无机器可读文本时返回能力不可用。知识服务当前为精确检索，不包含向量召回和重排。DiaMond 真实推理未验收，不能在论文或报告中写成“已完成真实影像模型推理”。

