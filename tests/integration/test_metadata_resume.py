from __future__ import annotations

from pathlib import Path

from multi_agent.application.metadata_service import MetadataService
from multi_agent.mapping.lifecycle import MappingLifecycleService
from multi_agent.mapping.semantic_validation import SemanticIssue, SemanticValidationReport


def test_metadata_submission_is_idempotent(tmp_path) -> None:
    service = MetadataService(tmp_path / "metadata.json")

    first = service.submit(
        question_id="q_score_type",
        answer="score is raw total for XX-v1",
        source="fixture dictionary v1",
        idempotency_key="metadata-submit-1",
    )
    second = service.submit(
        question_id="q_score_type",
        answer="score is raw total for XX-v1",
        source="fixture dictionary v1",
        idempotency_key="metadata-submit-1",
    )

    assert first == second


def test_questions_cli_payload_is_specific(tmp_path) -> None:
    service = MetadataService(tmp_path / "metadata.json")
    questions = service.list_questions(Path("tests/fixtures/stage03/metadata_questions.json"))

    assert questions[0].source_path == "score"
    assert "raw total" in questions[0].candidate_meaning
    assert questions[0].required_material


def test_needs_metadata_record_can_resume_to_validated_state() -> None:
    lifecycle = MappingLifecycleService()
    semantic_needs = SemanticValidationReport(
        status="needs_metadata",
        issues=[
            SemanticIssue(
                code="SCORE_TYPE_AMBIGUOUS",
                message="score type needs source dictionary",
                field_path="applicability.score_type",
                severity="needs_metadata",
            )
        ],
        instrument_id="xx-v1",
        instrument_definition_version="xx-v1:1",
    )
    semantic_valid = SemanticValidationReport(
        status="valid",
        issues=[],
        instrument_id="xx-v1",
        instrument_definition_version="xx-v1:1",
    )
    from multi_agent.mapping.candidate import MappingCandidate
    from multi_agent.mapping.spec import MappingSpec

    candidate = MappingCandidate(
        candidate_id="candidate1",
        status="proposed",
        spec=MappingSpec.model_validate(
            {
                "mapping_id": "candidate1",
                "version": "candidate1/1",
                "source_selector": {"kind": "rows"},
                "identity_field": "patient_number",
                "event_time_field": "visit_date",
                "record_id_field": "record_id",
                "bindings": [{"concept_id": "xx_v1.total", "source_field": "score", "transform": "parse_number"}],
                "constraints": {},
                "applicability": {"instrument_version": "1", "score_type": "raw_total"},
            }
        ),
        model_name="fake",
        prompt_version="stage03-mapping-candidate/1",
    )

    record = lifecycle.validate(lifecycle.submit(candidate), semantic_needs)
    record = lifecycle.validate(record, semantic_valid)
    record = lifecycle.activate(record)

    assert record.state == "active"
