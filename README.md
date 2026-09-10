# Multi-agent RWE 分析

## RWE 患者工作台（本地 8081）

```powershell
python -m pip install -e ".[rwe]"
python run_dashboard.py
```

打开 `http://127.0.0.1:8766`，输入 RWE **患者编号**（例如 `041_S_4060`，不是数据库内部数字 ID）。服务按顺序执行：RWE 导出 → 本地 JSON → 字段观测与证据仓 → v2 Scheduler → ReportSnapshot → 页面展示。

本地连接配置写入被 Git 忽略的 `.env.rwe.local`，支持 `RWE_API_BASE_URL`（默认 `http://localhost:8081`）、`RWE_API_TOKEN`、`RWE_PROJECT_ID`（默认 8）以及 `RWE_DB_HOST`、`RWE_DB_PORT`、`RWE_DB_NAME`、`RWE_DB_USER`、`RWE_DB_PASSWORD`。环境变量优先于配置文件，每次任务重新读取配置。数据库只用于只读解析患者编号；9 张表单通过 `/form/queryData` 读取。

Token 到期时重新登录（交互输入密码，不保存登录密码）：

```powershell
python tools/rwe_login.py --phone <手机号>
```

也可以分步导出、分析已保存的 JSON：

```powershell
python tools/export_rwe_patient.py --patient-number 041_S_4060 --output output/patient.json
python main.py output/patient.json --v2-goal rwe_patient_summary --data-dir output/rwe-cli --output output/analysis.json
```

网页运行产物位于 `output/rwe/runs/<job_id>/`：`patient.json` 是完整来源导出，`report.json` 是报告快照，`analysis.json` 包含页面数据、任务结果和字段证据；SQLite 与资产仓保留在同一目录。每次运行独立存储，不混入其他患者或旧版导出的观测。页面可下载来源 JSON 和报告，刷新后恢复最近任务；服务重启会将中断任务标记为失败，需重新运行。

`rwe_patient_summary` 是新增的真实表单描述分支，复用现有任务调度、证据契约、质询发布和报告快照；不将 MOCA/MMSE 等字段映射成测试用 XX-v1。当前输出为来源分数、同字段数值差和实验室/遗传记录，不进行条目重计分、诊断分级或临床变化判定。没有来源总分、文本、影像或已核验量表版本时保留限制；本分支不调用 LLM、RAG 或 DiaMond 推理。原 `multimodal_summary` 与旧 Agent 流程保留。

网页服务只监听 `127.0.0.1`，仅提供指定静态文件与本次任务产物，不暴露仓库和本机配置。

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
