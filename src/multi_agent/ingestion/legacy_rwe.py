from __future__ import annotations

from multi_agent.domain.mapping import ParsedDocument, ParsedRecord


def legacy_rwe_records(document: ParsedDocument, form_name: str) -> list[ParsedRecord]:
    if not isinstance(document.root, dict):
        raise ValueError("legacy RWE adapter expects a JSON object")
    records = document.root.get(form_name)
    if not isinstance(records, list):
        raise ValueError(f"legacy RWE form is not a list: {form_name}")
    patient = document.root.get("patient") if isinstance(document.root.get("patient"), dict) else {}
    parsed: list[ParsedRecord] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        data = dict(record)
        data.setdefault("patient_number", patient.get("patient_number"))
        locators = {field: f"$.{form_name}[{index}].{field}" for field in record}
        if "patient_number" in data:
            locators["patient_number"] = "$.patient.patient_number"
        parsed.append(
            ParsedRecord(
                data=data,
                record_locator=f"$.{form_name}[{index}]",
                value_locators=locators,
            )
        )
    return parsed
