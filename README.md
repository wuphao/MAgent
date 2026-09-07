# Multi-agent RWE 分析

本项目当前默认入口已经切换到 v2：以稳定数据契约、证据仓、任务 DAG、质询复核和报告快照为核心。旧 Agent 流程仍保留，可用 `--engine legacy` 显式运行。

## v2 默认流程

CSV/JSON/XLSX 等结构化数据通过 mapping 配置接入，然后运行目标分析：

```powershell
python main.py tests\fixtures\stage06\xx_v1_scoring_conflict.csv `
  --mapping configs\mappings\xx_v1_csv_long.json `
  --project-id demo `
  --source-namespace csv `
  --v2-goal multi_source_summary `
  --output output\demo_v2.json
```

常用目标：

- `source_inventory`：只做来源盘点，不需要 mapping。
- `xx_v1_assessment`：运行 XX-v1 质量检查和计分。
- `longitudinal_xx_v1`：运行 XX-v1 total 纵向描述。
- `multi_source_summary`：运行专业 Agent、质询复核和报告快照。
- `multimodal_summary`：在综合报告前额外接入文本、知识和影像兼容性任务。

并行调度：

```powershell
python main.py data.csv --mapping configs\mappings\xx_v1_csv_long.json --v2-goal multimodal_summary --parallel
```

## v2 架构能力

已经实现并验收：

- 数据契约：Asset、Observation、Evidence、Finding、Task、Challenge、ReportSnapshot。
- 多结构适配：JSON、CSV long、XLSX wide、nested JSON。
- 语义映射候选和元数据补充恢复。
- 任务 DAG、预算、重试、取消、串行/并行调度。
- 专业 Agent：质量检查、XX-v1 计分、纵向描述、实验室/遗传描述。
- 协作闭环：冲突发现、质询、定向复核、限制发布。
- 文本解析、知识检索、影像兼容性验证。
- 本地恢复：租约 fencing token、outbox 去重、staging 产物修复、依赖闭包和局部重算计划。
- 纯 Python API service：项目隔离、幂等键、运行创建、报告、质询和证据查询。

能力边界见：

- `docs/运行与恢复/能力可用清单.md`
- `evaluation/stage-08/shadow-cutover.md`

## 旧流程

旧流程仍可运行：

```powershell
python main.py --engine legacy output\patient_041_S_4060_analysis.json --full --output output\patient_041_S_4060_agent_result.json
```

旧流程可继续生成解释性报告：

```powershell
python generate_explainable_report.py output\patient_041_S_4060_analysis.json --no-llm
```

v2 报告入口读取同一个 `ReportSnapshot`，不会重新调用模型推断：

```powershell
python generate_explainable_report.py evaluation\stage-06\report_snapshot.json --v2-report-snapshot
python generate_agent_text_report.py evaluation\stage-06\report_snapshot.json --output output\report_from_snapshot.txt
```

## 影像说明

当前 v2 已完成 DiaMond 兼容性验证和拒绝路径。真实 DiaMond 推理需要真实 MRI/PET、模型权重、checkpoint hash、运行环境和资源日志；未满足这些条件时，系统不会把路径存在伪装成模型已运行。

详见：`evaluation/stage-07/imaging-compatibility.md`。

## 本地部署与恢复

配置示例：`configs/deployment/local.example.json`。

运维手册：`docs/运行与恢复/本地部署与恢复手册.md`。

默认部署形态是 CLI/API + SQLite + 本地资产仓 + 单机工作进程。共享数据库、对象仓和任务队列属于后续扩展，不把 SQLite 放到共享盘冒充多机可靠数据库。
