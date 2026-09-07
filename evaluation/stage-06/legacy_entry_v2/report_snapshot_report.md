# 多智能体协作分析报告

- 报告ID：report_2cdb2749f1075ef4b740
- Run ID：run_88f16ee919181c22039c
- 项目：stage06_eval
- 目标：multi_source_summary
- 状态：completed_with_limitations

## 覆盖情况

- 任务数：5
- 成功任务：assessment_xx_v1, longitudinal_xx_v1, quality_longitudinal, quality_xx_v1
- 失败任务：laboratory_optional
- Agent：AssessmentAgent, LaboratoryGeneticsAgent, LongitudinalAgent
- 未读证据数：0

## 发现

- **finding_275076036f39bfc2d6d6**（unresolved，引用数 6）：XX-v1 total remains disputed: recomputed total 4 differs from source reported total 0; no source amendment is available in this run.
  - 限制：reported and recomputed totals conflict; both values are retained
- **finding_f8953bb3e582e9fe405b**（active，引用数 6）：XX-v1 computed total matches reported total 6 on 2024-07-01.
- **finding_longitudinal_subject_a533e9f8d6b72c51ebff_xx_v1.total**（active，引用数 1）：XX-v1 total changed by 6 from 2024-01-01 to 2024-07-01 using 2 distinct dates.
  - 限制：two time points support descriptive change only

## 质询与复核

- **challenge_0afd25dbe40a82ac004e** [high/scoring]：该发现中工具重算总分 4 与来源报告总分 0 不一致；需要复核计分定义、条目完整性以及来源字段是否真的是总分。
  - 复核：unresolved；重算结果与来源报告值冲突，但当前没有原始字段定义修订或回查材料；按阶段06规则保留两个值，不任意替换。

## 局限性

- no reference rule is applied without platform and method metadata
- 重算结果与来源报告值冲突，但当前没有原始字段定义修订或回查材料；按阶段06规则保留两个值，不任意替换。
- 发现 1 个待质询或已质询问题，报告结论按限制发布。

## 建议

- 保留每个命题的证据引用、工具产物版本和复核状态，避免只发布自然语言结论。
- 对计分冲突补充来源字段定义或人工复核记录，再重新运行受影响分支。
- 未决复核项应进入报告限制区，不能被渲染器改写成已解决。
