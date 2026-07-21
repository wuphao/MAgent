from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from agents.base_agent import BaseAgent
from tools.diamond_tool import DiamondTool


class ImagingAgent(BaseAgent):
    """Run DiaMond on manually supplied MRI/PET paths."""

    name = "影像Agent"

    def analyze(self, memory: dict[str, Any]) -> dict[str, Any]:
        imaging = memory["normalized_case"].get("imaging") or {}
        mri = self._path_status(imaging.get("mri"), "MRI")
        pet = self._path_status(imaging.get("pet"), "PET")
        prediction: dict[str, Any] = {}
        error = None
        if mri["path_exists"] and pet["path_exists"]:
            patient = memory["normalized_case"].get("patient") or {}
            patient_number = str(patient.get("patient_number") or "patient")
            match = re.search(r"_(\d+)$", patient_number)
            rid = match.group(1) if match else str(patient.get("patient_id") or "")
            try:
                prediction = DiamondTool().run({
                    "mri_path": mri["path"],
                    "pet_path": pet["path"],
                    "sample_id": patient_number,
                    "rid": rid,
                })
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"

        if prediction.get("pred_label"):
            status = "prediction_completed"
            evidence = [{
                "form": "imaging_diamond",
                "record_id": None,
                "date": None,
                "finding": (
                    f"DiaMond预测={prediction.get('pred_label')}，"
                    f"概率={prediction.get('probabilities')}，"
                    f"置信度={prediction.get('confidence')}"
                ),
            }]
        elif error:
            status = "prediction_failed"
            evidence = []
        elif mri["path_provided"] or pet["path_provided"]:
            status = "paths_incomplete_or_not_found"
            evidence = []
        else:
            status = "awaiting_manual_paths"
            evidence = []
        return {
            "domain": "imaging",
            "status": status,
            "mri": mri,
            "pet": pet,
            "diamond_prediction": prediction or None,
            "prediction_error": error,
            "etiology_signal": prediction.get("risk_signal", "undetermined") if prediction else "undetermined",
            "evidence": evidence,
            "limitations": [
                "DiaMond输出是研究模型预测，不是临床诊断",
                "输入MRI/PET必须与模型训练预处理和模态要求相容",
                "当前不单独生成PET SUVR/Centiloid或MRI分区体积",
            ],
        }

    @staticmethod
    def _path_status(value: Any, modality: str) -> dict[str, Any]:
        if isinstance(value, dict):
            raw_path = value.get("path")
        else:
            raw_path = value
        path = str(raw_path or "").strip()
        exists = Path(path).exists() if path else False
        return {
            "modality": modality,
            "path": path,
            "path_provided": bool(path),
            "path_exists": exists,
            "analysis_status": (
                "path_verified_analysis_pending" if exists
                else "path_not_found" if path
                else "path_pending_manual_input"
            ),
        }
