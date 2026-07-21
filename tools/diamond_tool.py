import csv
import hashlib
import os
import re
import subprocess
from pathlib import Path

from config import (
    DIAMOND_CHECKPOINT,
    DIAMOND_DEVICE,
    DIAMOND_OUTPUT_DIR,
    DIAMOND_PREDICT_SCRIPT,
    DIAMOND_PYTHON,
)


class DiamondTool:
    label_map = {0: "CN", 1: "MCI", 2: "AD"}
    risk_map = {"CN": "低", "MCI": "中", "AD": "高"}

    def __init__(
        self,
        predict_script: str | None = None,
        checkpoint_path: str | None = None,
        output_dir: Path | None = None,
        device: str | None = None,
        python_executable: str | None = None,
        batch_size: int = 1,
    ):
        self.predict_script = Path(predict_script or DIAMOND_PREDICT_SCRIPT)
        self.checkpoint_path = Path(checkpoint_path or DIAMOND_CHECKPOINT) if (checkpoint_path or DIAMOND_CHECKPOINT) else None
        self.output_dir = Path(output_dir or DIAMOND_OUTPUT_DIR)
        self.device = device or DIAMOND_DEVICE
        self.python_executable = Path(python_executable or DIAMOND_PYTHON)
        self.adapter_script = Path(__file__).resolve().with_name("diamond_h5_adapter.py")
        self.batch_size = batch_size

    def run(self, inputs):
        if not isinstance(inputs, dict):
            return {}

        prediction = inputs.get("diamond_prediction")
        if isinstance(prediction, dict):
            return self._normalize_prediction(prediction)

        csv_path = inputs.get("diamond_prediction_csv")
        if csv_path:
            return self._read_prediction_csv(Path(csv_path))

        h5_path = inputs.get("diamond_h5_path") or inputs.get("h5_path")
        mri_path = inputs.get("mri_path")
        pet_path = inputs.get("pet_path")
        sample_id = str(inputs.get("sample_id") or inputs.get("patient_number") or "patient")
        rid = str(inputs.get("rid") or "")
        if not h5_path and mri_path and pet_path:
            h5_path, cached_csv, adapter_stdout = self._prepare_from_paths(
                Path(mri_path), Path(pet_path), sample_id, rid
            )
            if cached_csv is not None:
                result = self._read_prediction_csv(cached_csv)
                result.update({"cached": True, "h5_path": str(h5_path), "adapter_stdout": adapter_stdout})
                return result
        if not h5_path:
            return {}

        if not self.predict_script.exists():
            raise FileNotFoundError(f"DiaMond 预测脚本不存在: {self.predict_script}")
        if self.checkpoint_path is None:
            raise ValueError(
                "缺少 DiaMond checkpoint。请设置 DIAMOND_CHECKPOINT，"
                "或者在 raw_inputs 里提供 diamond_prediction/diamond_prediction_csv。"
            )
        if not self.checkpoint_path.exists():
            raise FileNotFoundError(f"DiaMond checkpoint 不存在: {self.checkpoint_path}")
        if not self.python_executable.exists():
            raise FileNotFoundError(f"DiaMond Python解释器不存在: {self.python_executable}")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        h5_path = Path(h5_path)
        output_csv = h5_path.with_name(h5_path.stem.replace("_input", "") + "_prediction.csv")

        command = [
            str(self.python_executable),
            str(self.predict_script),
            "--h5",
            str(h5_path),
            "--checkpoint",
            str(self.checkpoint_path),
            "--output-csv",
            str(output_csv),
            "--device",
            str(self.device),
            "--batch-size",
            str(self.batch_size),
        ]
        completed = self._run_command(command, "DiaMond预测")
        result = self._read_prediction_csv(output_csv)
        if completed.stdout:
            result["stdout"] = completed.stdout.strip()
        if completed.stderr:
            result["stderr"] = completed.stderr.strip()
        result["source_csv"] = str(output_csv)
        result["h5_path"] = str(h5_path)
        result["checkpoint"] = str(self.checkpoint_path)
        result["device"] = self.device
        result["cached"] = False
        return result

    def _prepare_from_paths(
        self,
        mri_path: Path,
        pet_path: Path,
        sample_id: str,
        rid: str,
    ) -> tuple[Path, Path | None, str]:
        if not self.adapter_script.exists():
            raise FileNotFoundError(f"DiaMond H5适配器不存在: {self.adapter_script}")
        if not self.python_executable.exists():
            raise FileNotFoundError(f"DiaMond Python解释器不存在: {self.python_executable}")
        if not mri_path.exists():
            raise FileNotFoundError(f"MRI路径不存在: {mri_path}")
        if not pet_path.exists():
            raise FileNotFoundError(f"PET路径不存在: {pet_path}")
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", sample_id).strip("._") or "patient"
        signature_source = "|".join([
            str(mri_path.resolve()), str(pet_path.resolve()),
            str(self.checkpoint_path.resolve()) if self.checkpoint_path else "",
        ])
        signature = hashlib.sha256(signature_source.encode("utf-8")).hexdigest()[:12]
        self.output_dir.mkdir(parents=True, exist_ok=True)
        h5_path = self.output_dir / f"{safe_id}_{signature}_input.h5"
        prediction_csv = self.output_dir / f"{safe_id}_{signature}_prediction.csv"
        if h5_path.exists() and prediction_csv.exists():
            return h5_path, prediction_csv, "使用已有H5和预测缓存"
        command = [
            str(self.python_executable), str(self.adapter_script),
            "--mri", str(mri_path), "--pet", str(pet_path),
            "--output-h5", str(h5_path), "--sample-id", safe_id,
            "--rid", rid,
        ]
        completed = self._run_command(command, "MRI/PET转DiaMond H5")
        return h5_path, None, completed.stdout.strip()

    @staticmethod
    def _run_command(command: list[str], label: str) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "无错误输出").strip()
            raise RuntimeError(f"{label}失败(exit={completed.returncode}): {detail}")
        return completed

    def _read_prediction_csv(self, csv_path: Path):
        if not csv_path.exists():
            raise FileNotFoundError(f"DiaMond 预测结果 CSV 不存在: {csv_path}")

        with csv_path.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            return {}
        return self._normalize_row(rows[-1], source_csv=str(csv_path))

    def _normalize_prediction(self, prediction):
        pred_label = prediction.get("pred_label") or prediction.get("label")
        pred_idx = prediction.get("pred_idx")
        if pred_label is None and pred_idx is not None:
            pred_label = self.label_map.get(int(pred_idx), str(pred_idx))
        return self._normalize_row(
            {
                "pred_idx": pred_idx if pred_idx is not None else "",
                "pred_label": pred_label or "",
                "sample_id": prediction.get("sample_id", ""),
                "rid": prediction.get("rid", ""),
                "true_dx": prediction.get("true_dx", ""),
                "prob_0": prediction.get("prob_0", prediction.get("prob_CN", "")),
                "prob_1": prediction.get("prob_1", prediction.get("prob_MCI", "")),
                "prob_2": prediction.get("prob_2", prediction.get("prob_AD", "")),
            },
            source_csv=prediction.get("source_csv", ""),
        )

    def _normalize_row(self, row, source_csv=""):
        pred_label = str(row.get("pred_label", "")).strip()
        pred_idx_raw = row.get("pred_idx", "")
        try:
            pred_idx = int(float(pred_idx_raw))
        except (TypeError, ValueError):
            pred_idx = None

        probs = {}
        for key in ("prob_0", "prob_1", "prob_2"):
            value = row.get(key, "")
            try:
                probs[key] = float(value)
            except (TypeError, ValueError):
                probs[key] = None

        if not pred_label and pred_idx is not None:
            pred_label = self.label_map.get(pred_idx, str(pred_idx))

        risk_signal = self.risk_map.get(pred_label, "中")
        abnormal = pred_label != "CN" if pred_label else False

        return {
            "sample_id": row.get("sample_id", ""),
            "rid": row.get("rid", ""),
            "true_dx": row.get("true_dx", ""),
            "pred_idx": pred_idx,
            "pred_label": pred_label,
            "probabilities": probs,
            "risk_signal": risk_signal,
            "abnormal": abnormal,
            "confidence": self._confidence_from_probs(probs),
            "source_csv": source_csv,
        }

    def _confidence_from_probs(self, probs):
        values = [value for value in probs.values() if isinstance(value, (int, float))]
        if not values:
            return None
        return max(values)
