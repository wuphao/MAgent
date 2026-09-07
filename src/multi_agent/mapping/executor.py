from __future__ import annotations

import hashlib
from typing import Any

from multi_agent.domain.assets import SourceLocator
from multi_agent.domain.mapping import CandidateBatch, CandidateObservation, ParsedDocument, ParsedRecord, QuarantinedRecord
from multi_agent.mapping.operators import parse_number, parse_string
from multi_agent.mapping.spec import Binding, MappingSpec
from multi_agent.ingestion.legacy_rwe import legacy_rwe_records


TRANSFORMS = {
    "parse_number": parse_number,
    "parse_string": parse_string,
}


class MappingExecutor:
    def execute(self, spec: MappingSpec, document: ParsedDocument) -> CandidateBatch:
        records = self._select_records(spec, document)
        candidates: list[CandidateObservation] = []
        quarantined: list[QuarantinedRecord] = []
        mapped_fields = {
            spec.identity_field,
            spec.event_time_field,
            spec.record_id_field,
        }
        operator_counts = {
            "select": {"input": len(document.records), "output": len(records), "failed": 0},
            "transform": {"input": 0, "output": 0, "failed": 0},
        }
        for record in records:
            subject_key = _string_value(record.data.get(spec.identity_field))
            record_key = _string_value(record.data.get(spec.record_id_field)) or record.record_locator
            event_value = _string_value(record.data.get(spec.event_time_field))
            if not subject_key:
                quarantined.append(_quarantine("MISSING_SUBJECT", record, spec.identity_field, record.data.get(spec.identity_field)))
                continue
            for binding in spec.bindings:
                mapped_fields.update(field for field in (binding.source_field, binding.concept_field, binding.value_field) if field)
                operator_counts["transform"]["input"] += 1
                concept_id = self._concept_id(binding, record)
                raw_value = self._raw_value(binding, record)
                if concept_id is None:
                    operator_counts["transform"]["failed"] += 1
                    quarantined.append(_quarantine("MISSING_CONCEPT", record, binding.concept_field or "concept", None))
                    continue
                transform = TRANSFORMS[binding.transform]
                result = transform(raw_value)
                if result.value is None:
                    operator_counts["transform"]["failed"] += 1
                    quarantined.append(
                        _quarantine(
                            result.error_code or "CONVERSION_FAILED",
                            record,
                            binding.source_field or binding.value_field or concept_id,
                            raw_value,
                            result.message or "conversion failed",
                        )
                    )
                    continue
                value_field = binding.source_field or binding.value_field or concept_id
                source = SourceLocator(
                    asset_id=document.asset_id,
                    asset_revision=document.asset_revision,
                    record_locator=record.record_locator,
                    value_locator=record.value_locators.get(value_field, f"{record.record_locator}.{value_field}"),
                    parser_version=document.parser_version,
                    locator_type="json_path" if document.layout == "json" else "record",
                )
                idempotency_key = _stable_id(
                    "observation-key",
                    document.asset_id,
                    str(document.asset_revision),
                    record.record_locator,
                    concept_id,
                    spec.version,
                    value_field,
                )
                candidates.append(
                    CandidateObservation(
                        project_id=document.project_id,
                        subject_ref=_stable_id("subject", document.project_id, document.source_namespace, subject_key),
                        source_subject_key=subject_key,
                        concept_id=concept_id,
                        value=result.value,
                        event_time=event_value,
                        event_time_precision="date" if event_value else "unknown",
                        source=source,
                        idempotency_key=idempotency_key,
                        mapping_revision=spec.version,
                        record_key=record_key,
                    )
                )
                operator_counts["transform"]["output"] += 1
        unmapped_fields = sorted(
            {
                field
                for record in records
                for field in record.data
                if field not in mapped_fields
            }
        )
        return CandidateBatch(
            project_id=document.project_id,
            mapping_id=spec.mapping_id,
            mapping_revision=spec.version,
            total_records=len(records),
            candidates=candidates,
            quarantined=quarantined,
            operator_counts=operator_counts,
            unmapped_fields=unmapped_fields,
        )

    def _select_records(self, spec: MappingSpec, document: ParsedDocument) -> list[ParsedRecord]:
        selector = spec.source_selector
        if selector.kind == "rows":
            return document.records
        if selector.kind == "legacy_json_list":
            if selector.path is None:
                raise ValueError("legacy_json_list requires path")
            return legacy_rwe_records(document, selector.path.removeprefix("$."))
        if selector.kind == "nested_json_records":
            return _nested_records(document, selector.subject_list_path or "$.subjects", selector.records_field or "records")
        raise ValueError(f"unsupported selector: {selector.kind}")

    def _concept_id(self, binding: Binding, record: ParsedRecord) -> str | None:
        if binding.concept_field:
            value = record.data.get(binding.concept_field)
            return str(value).strip() if value not in (None, "") else None
        return binding.concept_id

    def _raw_value(self, binding: Binding, record: ParsedRecord) -> Any:
        if binding.value_field:
            return record.data.get(binding.value_field)
        if binding.source_field:
            return record.data.get(binding.source_field)
        return None


def _nested_records(document: ParsedDocument, subject_list_path: str, records_field: str) -> list[ParsedRecord]:
    if subject_list_path != "$.subjects" or not isinstance(document.root, dict):
        raise ValueError("stage02 nested selector supports $.subjects")
    subjects = document.root.get("subjects")
    if not isinstance(subjects, list):
        raise ValueError("nested document has no subjects array")
    selected: list[ParsedRecord] = []
    for subject_index, subject in enumerate(subjects):
        if not isinstance(subject, dict):
            continue
        records = subject.get(records_field)
        if not isinstance(records, list):
            continue
        for record_index, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            data = dict(record)
            data.setdefault("patient_number", subject.get("patient_number"))
            record_locator = f"$.subjects[{subject_index}].{records_field}[{record_index}]"
            locators = {field: f"{record_locator}.{field}" for field in record}
            locators["patient_number"] = f"$.subjects[{subject_index}].patient_number"
            selected.append(ParsedRecord(data=data, record_locator=record_locator, value_locators=locators))
    return selected


def _quarantine(
    code: str,
    record: ParsedRecord,
    field_path: str,
    raw_value: Any,
    message: str | None = None,
) -> QuarantinedRecord:
    return QuarantinedRecord(
        code=code,
        message=message or code,
        record_locator=record.record_locator,
        field_path=field_path,
        raw_value=raw_value,
    )


def _string_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"
