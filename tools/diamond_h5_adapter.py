"""Build a one-sample DiaMond H5 file from MRI and PET paths."""

from __future__ import annotations

import argparse
from pathlib import Path

import h5py
import numpy as np
import SimpleITK as sitk


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mri", type=Path, required=True)
    parser.add_argument("--pet", type=Path, required=True)
    parser.add_argument("--output-h5", type=Path, required=True)
    parser.add_argument("--sample-id", required=True)
    parser.add_argument("--rid", default="")
    return parser.parse_args()


def dicom_directories(root: Path) -> list[Path]:
    if root.is_file():
        return []
    candidates: list[Path] = []
    for current, _, files in __import__("os").walk(root):
        if any(name.lower().endswith((".dcm", ".ima")) for name in files):
            candidates.append(Path(current))
            continue
        try:
            if sitk.ImageSeriesReader.GetGDCMSeriesIDs(current):
                candidates.append(Path(current))
        except RuntimeError:
            pass
    return candidates


def read_dicom_series(directory: Path) -> np.ndarray:
    reader = sitk.ImageSeriesReader()
    series_ids = reader.GetGDCMSeriesIDs(str(directory)) or []
    if not series_ids:
        raise RuntimeError(f"没有找到DICOM序列: {directory}")
    best_files: tuple[str, ...] = ()
    for series_id in series_ids:
        files = tuple(reader.GetGDCMSeriesFileNames(str(directory), series_id))
        if len(files) > len(best_files):
            best_files = files
    if not best_files:
        raise RuntimeError(f"DICOM序列没有可读取文件: {directory}")
    reader.SetFileNames(best_files)
    return np.asarray(sitk.GetArrayFromImage(reader.Execute()), dtype=np.float32)


def read_volume(path: Path, modality: str) -> tuple[np.ndarray, str]:
    if not path.exists():
        raise FileNotFoundError(f"{modality}路径不存在: {path}")
    if path.is_file():
        lowered = path.name.lower()
        if lowered.endswith((".nii", ".nii.gz", ".mha", ".mhd", ".nrrd")):
            array = np.asarray(sitk.GetArrayFromImage(sitk.ReadImage(str(path))), dtype=np.float32)
            np.nan_to_num(array, copy=False)
            return array, str(path.resolve())
        raise ValueError(f"{modality}文件格式不支持: {path}; 支持DICOM目录或NIfTI/MHA/NRRD文件")
    candidates = dicom_directories(path)
    if not candidates:
        raise RuntimeError(f"{modality}目录下未找到DICOM序列: {path}")
    ranked = []
    for directory in candidates:
        try:
            series_ids = sitk.ImageSeriesReader.GetGDCMSeriesIDs(str(directory)) or []
            count = max(
                (len(sitk.ImageSeriesReader.GetGDCMSeriesFileNames(str(directory), sid)) for sid in series_ids),
                default=0,
            )
            ranked.append((count, directory))
        except RuntimeError:
            continue
    if not ranked:
        raise RuntimeError(f"{modality}目录下没有可读取的DICOM序列: {path}")
    _, selected = max(ranked, key=lambda item: (item[0], str(item[1])))
    array = read_dicom_series(selected)
    np.nan_to_num(array, copy=False)
    return array, str(selected.resolve())


def main() -> int:
    args = parse_args()
    mri, selected_mri = read_volume(args.mri, "MRI")
    pet, selected_pet = read_volume(args.pet, "PET")
    # DiaMond passes stored arrays through TorchIO before adding the batch
    # dimension. TorchIO expects channel-first 4D medical images.
    if mri.ndim == 3:
        mri = mri[np.newaxis, ...]
    if pet.ndim == 3:
        pet = pet[np.newaxis, ...]
    args.output_h5.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(args.output_h5, "w") as h5:
        sample = h5.create_group(args.sample_id)
        sample.create_group("MRI").create_group("T1").create_dataset(
            "data", data=mri, compression="gzip", compression_opts=4
        )
        sample.create_group("PET").create_group("FDG").create_dataset(
            "data", data=pet, compression="gzip", compression_opts=4
        )
        sample.attrs["DX"] = ""
        sample.attrs["RID"] = args.rid
        sample.attrs["MRI_PATH"] = selected_mri
        sample.attrs["PET_PATH"] = selected_pet
    print(f"MRI_SELECTED={selected_mri}")
    print(f"PET_SELECTED={selected_pet}")
    print(f"H5_OUTPUT={args.output_h5.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
