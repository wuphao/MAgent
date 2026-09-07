# v2 代码审查报告

## 审查范围

本次审查按 `docs/改造行动方案` 中 01—08 阶段设计与行动文档反查代码，覆盖入口、领域模型、数据接入、映射、专业能力、调度、协作报告、文本/知识/影像、恢复/API/默认切换和验收产物。

## 已修复问题

1. `ReportPublisher` 修订发现时，原实现把同一个 `finding_id` 同时放入 `findings` 和 `withdrawn_finding_ids`。这与“旧发现保留但从新发布候选中排除”的设计冲突。已修为：复核后的发现使用 `_reviewed` 新 id，原始 finding_id 进入 withdrawn 列表，并新增回归断言保证两者不相交。
2. `ApplicationAPI.get_report` 与 `cancel_run` 原先只校验传入 project_id 是否在用户权限内，没有确认 run_id 属于该 project。已新增 `TaskStore.get_run()` 与 `_authorize_run()`，报告查询和取消都会做仓储归属检查，避免跨项目 run_id 混淆。
3. `ApplicationAPI.create_analysis_run` 对非法 goal 原先会抛出 Pydantic 异常。已改为结构化 `VALIDATION_FAILED` 响应。
4. `TaskStore.create_run` 原先使用 `INSERT OR REPLACE`，同一 run_id 重建会擦除已有任务状态和结果，与恢复/历史查询目标冲突。已改为 `INSERT OR IGNORE`，并新增幂等创建回归测试。
5. `TaskStore` 新建表结构原先不直接包含 lease 字段，只能通过 `LeaseStore` 单独补迁移。已将 `lease_owner`、`lease_expires_at`、`attempt_id`、`fencing_token` 纳入基础迁移，并保留前向补列。
6. 第七阶段新增 `ingestion/parsers/` 包后，旧 `ingestion/parsers.py` 成为不会被 Python 加载的影子文件。已删除影子文件，保留包内 `Parser` 兼容导出，并新增 `parsers/pdf.py` 包装入口以贴合阶段文档。
7. `KnowledgeAgent` 和 `ImagingAgent` 原先只从 `task_results` 读取配置。已新增 `TaskContext.task_parameters`，调度器按当前任务传入 `parameters`，使 Agent 能自然接收具体问题、知识目录和影像参数。

## 与设计一致的部分

- v2 Agent 面向 Observation、Evidence、ToolArtifact、Finding 工作，没有直接读取旧 `raw_case` / `normalized_case`。
- 映射执行使用声明式 MappingSpec 和受限算子，没有执行模型生成的任意 Python/SQL。
- 专业能力通过 CapabilitySpec 注册，demo/unavailable 能力不会进入生产可用列表。
- `SynthesisAgent` 接入阶段 05 DAG，读取同一 run 的上游结构化结果生成 ReportSnapshot。
- JSON、Markdown、TXT 报告均从同一个 ReportSnapshot 渲染；v2 报告入口不会重新调用 LLM 推断。
- 影像正式路径只做兼容性验证和拒绝，不把 `tools/mri_tool.py`、`tools/pet_tool.py` 的固定演示输出注册成生产能力。
- API 层有项目隔离、幂等冲突检测、run 归属校验和主体范围 evidence 查询。
- 恢复层覆盖租约 fencing token、过期 running 重排、outbox 去重、staging 产物 hash 修复和依赖影响闭包。

## 当前边界

- 真实 DiaMond 推理未交付：缺少真实 MRI/PET、checkpoint hash、模型权重、运行环境和资源日志。
- OCR 未实现：扫描 PDF 无可提取文字时返回 capability_unavailable。
- 知识服务是版本化 Markdown 精确检索，尚无向量召回、重排、冲突知识仲裁和自动规则激活。
- 当前 XX-v1 是合成测试量表，不等同于真实 MMSE/MoCA/FAQ/CDR/ADAS 全规则库。
- LLM 语义映射使用 FakeModelGateway 验收；真实 DeepSeek/其他模型调用未作为 v2 自动验收路径。
- Scheduler 仍使用状态机执行，LeaseStore 已实现并测试，但尚未把所有调度领取动作改为强制 lease claim 模式。
- API 是纯 Python service，没有 HTTP/FastAPI 包装、认证中间件和分页游标持久化。
- 增量重算目前生成受影响任务集合，尚未实现跨运行自动重放和报告历史 UI。
- 多机数据库/对象仓/队列部署未实现；当前交付形态是 SQLite + 本地资产仓 + 单机工作进程。

## 验证结果

- 全量测试：65 passed, 1 skipped in 5.01s。
- 编译检查通过。
- 敏感词扫描仅命中正常业务错误码 `BUDGET_TOKENS_EXCEEDED` 和本报告中的同名说明。

