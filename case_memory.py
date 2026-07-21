from __future__ import annotations

from typing import Any


def init_case_memory(raw_case: dict[str, Any]) -> dict[str, Any]:
    patient = raw_case.get("patient") or {}
    return {
        "case_id": patient.get("patient_number") or patient.get("patient_id") or "unknown",
        "raw_case": raw_case,
        "normalized_case": {},
        "agent_outputs": {},
        "final_report": {},
    }
