# XX-v1 测试量表说明

XX-v1 total 表示四个条目的求和。若来源字段名为 total 但数值与条目和不一致，应先复核字段定义和记录定位，不能直接覆盖原始值。

缺失条目不能按 0 自动填补。缺失原因应保留到 observation metadata，并由评分能力返回 insufficient 或 limitation。
