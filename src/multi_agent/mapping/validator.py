from __future__ import annotations

from multi_agent.domain.mapping import CandidateBatch, ValidationReport


class MappingValidator:
    def validate(self, batch: CandidateBatch) -> ValidationReport:
        checked = 0
        for candidate in batch.candidates:
            if candidate.source.record_locator and candidate.source.value_locator:
                checked += 1
        status = "valid"
        if batch.quarantined and batch.candidates:
            status = "partial"
        elif batch.quarantined and not batch.candidates:
            status = "invalid"
        return ValidationReport(
            status=status,
            total_records=batch.total_records,
            published_count=len(batch.candidates),
            quarantined_count=len(batch.quarantined),
            operator_counts=batch.operator_counts,
            unmapped_fields=batch.unmapped_fields,
            quarantined=batch.quarantined,
            source_locators_checked=checked,
        )
