# Multi-agent RWE分析

## 生成可解释性报告

大模型解释改为调用 DeepSeek 官方 API，不再依赖本地 Ollama。先在 PowerShell 中配置 API Key：

```powershell
$env:DEEPSEEK_API_KEY="你的DeepSeek API Key"
```

默认模型为 `deepseek-v4-flash`，可按需覆盖：

```powershell
$env:DEEPSEEK_MODEL="deepseek-v4-pro"
```

生成 JSON 和 Markdown 报告：

```powershell
python generate_explainable_report.py output\patient_041_S_4060_analysis.json
```

不调用大模型、仅使用确定性模板：

```powershell
python generate_explainable_report.py output\patient_041_S_4060_analysis.json --no-llm
```

报告默认保存在`output/reports`。量表值、日期、record_id、统计量和数据质量结论
由Python生成并锁定；大模型只解释已经存在的证据。

## Agent 流程

当前处理顺序为：数据质控、认知量表、功能分期、纵向统计、生物标志物、影像、临床整合。
患者导出 JSON 使用 `schema_version=2.0`，包含 MOCA、MMSE、FAQ、CDR、ADAS、
DICOM 基本信息、血浆、APOE 和脑脊液九张表。

影像路径需在导出 JSON 中手动填写：

```json
{
  "imaging": {
    "mri": {"path": "D:\\path\\to\\mri"},
    "pet": {"path": "D:\\path\\to\\pet"}
  }
}
```

`mri.path` 和 `pet.path` 均可填写 NIfTI/MHA/NRRD 文件，或包含 DICOM
序列的目录。影像 Agent 会自动选择目录中切片数最多的 DICOM 序列，转换为
DiaMond 所需的 H5，然后调用：

```text
D:\Python Project\DiaMond\DiaMond
```

默认使用 `models\DiaMond\mri+pet\DiaMond_multi_split4_bestval.pt` 和
DiaMond 自带的 `.venv` 在 CUDA 上预测，输出 CN/MCI/AD 及三类概率。可通过
`DIAMOND_ROOT`、`DIAMOND_PYTHON`、`DIAMOND_CHECKPOINT`、`DIAMOND_DEVICE`
环境变量覆盖。只有 MRI、PET 两个路径均有效时才运行模型；结果属于研究模型
输出，不应单独作为临床诊断。

先从 RWE 导出患者 JSON（文件会写入 `output`）：

```powershell
python rwe_data_tools\export_patient_agent_json.py --patient-number "041_S_4060"
```

手工填写该 JSON 的两个影像路径后，再运行完整 Agent 流程：

输出包含全部 Agent 中间结果：

```powershell
python main.py output\patient_041_S_4060_analysis.json --use-llm --full --output output\patient_041_S_4060_agent_result.json
```

最后直接读取上述已包含影像 Agent 结果的 JSON，将五个核心 Agent 结果交给
DeepSeek，并生成一段式 TXT 报告：

```powershell
python generate_agent_text_report.py `
  output\patient_041_S_4060_agent_result.json `
  --output output\patient_041_S_4060_report.txt
```
