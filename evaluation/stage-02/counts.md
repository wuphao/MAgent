# 阶段 02 计数对账

| 布局 | 输入 | 映射 | 选择记录数 | 发布观测数 | 隔离数 | 未映射字段 |
|---|---|---|---:|---:|---:|---|
| 旧 RWE JSON | `xx_v1_legacy_rwe.json` | `xx_v1_legacy_json/1` | 2 | 10 | 0 | `remark` |
| CSV 长表 | `xx_v1_csv_long.csv` | `xx_v1_csv_long/1` | 10 | 10 | 0 | `patient_name`, `remark` |
| Excel 宽表 | `xx_v1_wide.xlsx` | `xx_v1_xlsx_wide/1` | 2 | 10 | 0 | `patient_name`, `remark` |
| 嵌套 JSON | `xx_v1_nested.json` | `xx_v1_nested_json/1` | 2 | 10 | 0 | `remark` |

四种布局投影后的 `source_subject_key`、`record_key`、`event_time`、`concept_id`、`value` 完全一致。`subject_ref` 由于包含来源命名空间，允许不同；这保证不同来源的同名主体不会被自动合并。
