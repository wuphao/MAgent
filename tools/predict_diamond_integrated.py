"""DiaMond inference entry with the training-time RegBN dimensions restored."""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

import torch
import numpy as np


DIAMOND_ROOT = Path(os.getenv("DIAMOND_ROOT", r"D:\Python Project\DiaMond\DiaMond"))
DIAMOND_TOOLS = DIAMOND_ROOT / "tools"
if str(DIAMOND_TOOLS) not in sys.path:
    sys.path.insert(0, str(DIAMOND_TOOLS))

import predict_diamond as core


class CompatibleH5PredictDataset(core.H5PredictDataset):
    """Bridge DiaMond's legacy extra-axis behavior with current TorchIO."""

    def __getitem__(self, index: int):
        item = self._items[index]

        def transform(name: str):
            array = np.nan_to_num(item[name], copy=False)
            if array.ndim == 3:
                array = array[np.newaxis, ...]
            transformed = self.transform(array)
            return torch.as_tensor(transformed).float()

        if self.with_mri and self.with_pet:
            return (transform("mri"), transform("pet")), item
        if self.with_mri:
            return transform("mri"), item
        return transform("pet"), item


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Integrated DiaMond prediction.")
    parser.add_argument("--h5", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--batch-size", type=int, default=1)
    return parser.parse_args()


def scalar_at(value, index: int):
    if isinstance(value, torch.Tensor):
        item = value[index]
        return item.item() if item.numel() == 1 else item
    if isinstance(value, (list, tuple)):
        return value[index]
    return value


def main() -> int:
    args = parse_args()
    device = torch.device(args.device)
    checkpoint = torch.load(args.checkpoint, map_location=device)
    config = core.load_hyperparams(args.checkpoint)
    _, model, head, class_num, modality = core.build_model(config, checkpoint, device)
    feature_channels = 192 if class_num == 3 else 128
    regbn = core.RegBN(
        f_num_channels=feature_channels,
        g_num_channels=feature_channels,
        f_layer_dim=[],
        g_layer_dim=[],
        normalize_input=True,
        normalize_output=True,
        affine=True,
        sigma_THR=0.0,
        sigma_MIN=0.0,
    ).to(device)
    regbn.eval()

    dataset = CompatibleH5PredictDataset(args.h5, with_mri=True, with_pet=True)
    loader = torch.utils.data.DataLoader(dataset, batch_size=args.batch_size, shuffle=False)
    label_map = {0: "CN", 1: "MCI", 2: "AD"}
    rows = []
    for batch in loader:
        preds, probs, meta = core.predict_batch(batch, model, head, regbn, device, class_num, modality)
        for index, pred in enumerate(preds):
            pred_index = int(pred)
            row = {
                "sample_id": scalar_at(meta.get("sample_id", ""), index),
                "rid": scalar_at(meta.get("rid", ""), index),
                "true_dx": scalar_at(meta.get("dx", ""), index),
                "pred_idx": pred_index,
                "pred_label": label_map.get(pred_index, str(pred_index)),
            }
            for class_index in range(probs.shape[1]):
                row[f"prob_{class_index}"] = float(probs[index, class_index])
            rows.append(row)

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else ["sample_id", "rid", "true_dx", "pred_idx", "pred_label"]
    with args.output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} predictions to {args.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
