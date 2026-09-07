# 阶段 07 影像兼容性清单

## 已核查代码

- `tools/diamond_tool.py`：真实预测需要 `DIAMOND_PREDICT_SCRIPT`、`DIAMOND_CHECKPOINT`、`DIAMOND_PYTHON`、输入 H5、设备和 batch size。若提供 `diamond_prediction` 或 `diamond_prediction_csv`，旧工具会读取已有预测；这不能证明真实模型已运行。
- `tools/diamond_h5_adapter.py`：把 MRI 和 PET 路径转换为 H5，H5 结构包含 `MRI/T1/data` 与 `PET/FDG/data`。该脚本会读取 DICOM 或 NIfTI/MHA/NRRD，但当前代码按序列文件数选择候选，不能证明该序列一定符合模型训练要求。
- `tools/mri_tool.py`、`tools/pet_tool.py`：固定演示输出，不能作为正式影像能力注册。

## 阶段 07 已确认要求

- MRI 资产必须存在，并提供明确的序列身份；仅路径存在不足以运行 DiaMond。
- PET 资产必须存在，并确认示踪剂为 FDG 或 18F-FDG。
- DiaMond checkpoint hash 必须记录，缓存键不能只由路径或 mtime 决定。
- 缓存键包含 MRI 内容 hash、PET 内容 hash、checkpoint hash 和兼容性验证版本；替换同一路径文件内容会导致缓存失效。
- 不兼容或条件不明时返回 `capability_unavailable` / `incompatible`，不生成阴性影像结论。

## 尚未知项

- 真实模型训练时的空间分辨率、配准、强度归一化、裁剪尺寸和类别校准说明。
- 当前环境是否具备可用 GPU、匹配 Python 环境、完整权重文件和真实合格 MRI/PET 输入。
- 超时后是否能可靠终止完整子进程树，需要在目标平台用真实运行验证。

## 验收状态

阶段 07 已完成影像契约和拒绝路径验收。真实 DiaMond 推理未验证；需设置真实 MRI、PET 和 checkpoint hash 后运行：

```powershell
python -c "import sys; sys.path[:0]=['evaluation/stage-01/test-packages','src']; import pytest; raise SystemExit(pytest.main(['-m','real_imaging','tests/acceptance/test_imaging_runtime.py','-q']))"
```
