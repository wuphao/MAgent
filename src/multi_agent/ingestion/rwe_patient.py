"""Adapt exported RWE forms without inventing scores, units, or instrument versions."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date
from pathlib import Path

from multi_agent.domain.assets import SourceLocator
from multi_agent.domain.observations import Observation, TypedValue
from multi_agent.storage.assets import AssetManifest, AssetRepository
from multi_agent.storage.sqlite import EvidenceRepository, SQLiteStore


SCORE_FIELDS = {
    "moca": ("MOCA总分", "MoCA总分", "总分"),
    "mmse": ("MMSE总分",),
    "faq": ("总分",),
    "cdr": ("总体评分", "CDRSB总分"),
    "adas": ("ADAS-Cog 13 项总分", "ADAS-Cog 11 项总分"),
}


def stable_id(prefix: str, *parts: str) -> str:
    return prefix + "_" + hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:24]


def typed_value(value) -> TypedValue:
    if value is None or isinstance(value, str) and not value.strip():
        return TypedValue(value_type="missing", missing_reason="来源未填写")
    if isinstance(value, bool):
        return TypedValue(value_type="boolean", value=value)
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            return TypedValue(value_type="unknown", missing_reason="非有限数值")
        return TypedValue(value_type="number", value=value)
    # Preserve coded strings and comparators; only declared score fields are coerced later.
    return TypedValue(value_type="string", value=value if isinstance(value, str) else json.dumps(value, ensure_ascii=False))


def ingest_patient(path: Path, data_dir: Path, project_id: str, expected_patient: str) -> dict:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(document, dict) or not isinstance(document.get("patient"), dict):
        raise ValueError("JSON 缺少患者信息")
    if document["patient"].get("patient_number") != expected_patient:
        raise ValueError("JSON 患者编号与请求不一致")
    forms = document.get("forms")
    if not isinstance(forms, dict) or not forms:
        raise ValueError("JSON 缺少 RWE forms 数据")
    store = SQLiteStore(data_dir / "evidence.sqlite3")
    asset = AssetRepository(store, data_dir / "assets").register(
        AssetManifest(project_id, path, "rwe", "application/json")
    )
    observations, warnings, record_counts = [], [], {}
    for key, form in forms.items():
        if not isinstance(form, dict) or not isinstance(form.get("records"), list):
            raise ValueError(f"无效表单结构：{key}")
        records = form["records"]
        record_counts[key] = len(records)
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                raise ValueError(f"无效表单记录：{key}[{index}]")
            locator = f'$.forms[{json.dumps(key)}].records[{index}]'
            event_time = record.get("visit_date")
            if event_time:
                try:
                    event_time = date.fromisoformat(str(event_time)).isoformat()
                except ValueError:
                    event_time = None
            if not event_time and form.get("fill_mode") != "single":
                warnings.append(f"{form.get('form_name', key)} 第 {index + 1} 条记录缺少有效日期，未用于纵向变化。")
            for field, value in record.items():
                if field in {"record_id", "visit_date"}:
                    continue
                converted = typed_value(value)
                score = field in SCORE_FIELDS.get(key, ())
                if score and converted.value_type == "string":
                    try:
                        number = float(str(converted.value))
                        if math.isfinite(number):
                            converted = TypedValue(value_type="number", value=number)
                    except ValueError:
                        pass
                value_locator = f"{locator}[{json.dumps(field, ensure_ascii=False)}]"
                identity = stable_id("obs", project_id, asset.asset_id, value_locator)
                observations.append(Observation(
                    project_id=project_id, observation_id=identity,
                    subject_ref=f"rwe:{document.get('project', {}).get('id', 'unknown')}:{expected_patient}",
                    concept_id=f"rwe.{key}.{field}", value=converted, event_time=event_time,
                    event_time_precision="date" if event_time else "unknown", available_at=asset.available_at,
                    source=SourceLocator(asset_id=asset.asset_id, asset_revision=asset.revision,
                        record_locator=locator, value_locator=value_locator, locator_type="json_path",
                        parser_version="rwe-forms/1"),
                    idempotency_key=identity, mapping_revision="rwe-source-fields/1",
                    metadata={"form_key": key, "form_name": form.get("form_name", key),
                        "field": field, "record_id": record.get("record_id"), "reported_score": score,
                        "instrument_version": None, "source_value": value},
                ))
    if not observations:
        raise ValueError("患者没有可分析的表单字段")
    EvidenceRepository(store).publish(observations, [], stable_id("publish", project_id, asset.asset_id))
    return {"document": document, "asset": asset.model_dump(mode="json"),
        "observation_count": len(observations), "record_counts": record_counts, "warnings": warnings}
