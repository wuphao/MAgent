from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from multi_agent.domain.mapping import ValidationReport
from multi_agent.mapping.semantic_validation import SemanticValidationReport


class ValidationReportStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        report_id: str,
        structural: ValidationReport,
        semantic: SemanticValidationReport,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        path = self.root / f"{report_id}.json"
        payload = {
            "report_id": report_id,
            "structural": structural.model_dump(mode="json"),
            "semantic": semantic.model_dump(mode="json"),
            "metadata": metadata or {},
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load(self, report_id: str) -> dict[str, Any]:
        path = self.root / f"{report_id}.json"
        return json.loads(path.read_text(encoding="utf-8"))
