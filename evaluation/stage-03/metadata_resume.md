# 阶段 03 元数据补充记录

问题：`q_score_type`

补充说明：`score is raw total for XX-v1 version 1`

说明来源：`tests/fixtures/schema_variants/expected.json`

幂等键：`stage03-metadata-1`

生成修订：`metadata_54c2b57d2ca6873ea6ae`

效果：缺少分数类型与版本说明的候选映射可从 `needs_metadata` 重新进入语义验证；只有结构验证和语义验证均通过后，生命周期服务才允许进入 `active`。
