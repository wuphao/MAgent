from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from multi_agent.domain.mapping import CandidateBatch, SourceProfile, ValidationReport
from multi_agent.domain.instruments import InstrumentSpec
from multi_agent.mapping.spec import MappingSpec


class SemanticModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SemanticIssue(SemanticModel):
    code: str
    message: str
    field_path: str
    severity: Literal["error", "warning", "needs_metadata"] = "error"


class SemanticValidationReport(SemanticModel):
    status: Literal["valid", "needs_metadata", "invalid"]
    issues: list[SemanticIssue] = Field(default_factory=list)
    instrument_id: str
    instrument_definition_version: str


class SemanticValidator:
    def validate(
        self,
        spec: MappingSpec,
        batch: CandidateBatch,
        structural_report: ValidationReport,
        instrument: InstrumentSpec,
        profile: SourceProfile | None = None,
    ) -> SemanticValidationReport:
        issues: list[SemanticIssue] = []
        if structural_report.status == "invalid":
            issues.append(
                SemanticIssue(
                    code="STRUCTURE_INVALID",
                    message="semantic validation cannot override structural validation failure",
                    field_path="$",
                )
            )
        if instrument.status != "active":
            issues.append(
                SemanticIssue(
                    code="INSTRUMENT_NOT_ACTIVE",
                    message="instrument definition is not active",
                    field_path="instrument.status",
                    severity="needs_metadata",
                )
            )
        registered = set(instrument.concepts)
        for index, binding in enumerate(spec.bindings):
            if binding.concept_id != "from_field" and binding.concept_id not in registered:
                issues.append(
                    SemanticIssue(
                        code="CONCEPT_NOT_IN_INSTRUMENT",
                        message=f"{binding.concept_id} is not registered in {instrument.instrument_id}",
                        field_path=f"bindings[{index}].concept_id",
                    )
                )
        if spec.applicability.get("instrument_version") not in (None, instrument.version):
            issues.append(
                SemanticIssue(
                    code="INSTRUMENT_VERSION_CONFLICT",
                    message="mapping instrument_version conflicts with registered instrument definition",
                    field_path="applicability.instrument_version",
                    severity="needs_metadata",
                )
            )
        if spec.applicability.get("score_type") in {"unknown", "ambiguous"}:
            issues.append(
                SemanticIssue(
                    code="SCORE_TYPE_AMBIGUOUS",
                    message="score field role must distinguish raw total from adjusted or reported score",
                    field_path="applicability.score_type",
                    severity="needs_metadata",
                )
            )
        if spec.applicability.get("event_time_role") == "entry_date":
            issues.append(
                SemanticIssue(
                    code="EVENT_TIME_ROLE_INVALID",
                    message="entry date cannot be used as measurement event date without metadata",
                    field_path="applicability.event_time_role",
                    severity="needs_metadata",
                )
            )
        if profile and spec.applicability.get("unit") and profile.fields.get("unit"):
            sample_units = set(profile.fields["unit"].get("sample_values", []))
            expected_unit = spec.applicability["unit"]
            if sample_units and sample_units != {expected_unit}:
                issues.append(
                    SemanticIssue(
                        code="UNIT_CONFLICT",
                        message=f"profile units {sorted(sample_units)} do not match mapping unit {expected_unit}",
                        field_path="profile.fields.unit",
                        severity="needs_metadata",
                    )
                )

        if any(issue.severity == "error" for issue in issues):
            status = "invalid"
        elif issues:
            status = "needs_metadata"
        else:
            status = "valid"
        return SemanticValidationReport(
            status=status,
            issues=issues,
            instrument_id=instrument.instrument_id,
            instrument_definition_version=instrument.definition_version,
        )


def validation_record(
    structural: ValidationReport,
    semantic: SemanticValidationReport,
) -> dict[str, Any]:
    return {
        "structural": structural.model_dump(mode="json"),
        "semantic": semantic.model_dump(mode="json"),
    }
