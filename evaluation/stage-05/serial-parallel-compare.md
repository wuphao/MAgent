# 阶段 05 串并行对照

输入：`evaluation/stage-04/v2-store-verified/stage02.sqlite3`

串行输出：`evaluation/stage-05/run_serial.json`

并行输出：`evaluation/stage-05/run_parallel.json`

对照结果：两个运行的任务终态一致。Artifact ID 含执行时间戳，因此不要求逐字一致；确定性发现内容、任务状态和依赖行为一致。

并行执行只派发依赖已满足的独立分支。`quality_xx_v1`、`quality_longitudinal` 与 `laboratory_optional` 可并行；`assessment_xx_v1` 与 `longitudinal_xx_v1` 分别等待对应质量任务成功。
