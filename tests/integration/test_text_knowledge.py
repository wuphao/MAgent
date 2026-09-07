from __future__ import annotations

from pathlib import Path

from multi_agent.capabilities.text_validation import TextEvidenceValidator, TextObservationExtractor
from multi_agent.ingestion.manifest import InputManifest
from multi_agent.ingestion.parsers.text import TextParser
from multi_agent.knowledge import ExactRetriever, KnowledgeDocumentLoader, KnowledgeIndex, RuleCandidateBuilder
from multi_agent.orchestration.planner import TemplatePlanner
from multi_agent.domain.requests import AnalysisRequest
from datetime import datetime, timezone
from multi_agent.registries.capabilities import CapabilityRegistry
from multi_agent.orchestration.plan_validator import PlanValidator
from multi_agent.storage.assets import AssetRepository
from multi_agent.storage.sqlite import SQLiteStore


def test_text_parser_preserves_spans_and_extractor_marks_semantics(tmp_path: Path) -> None:
    parser = TextParser(AssetRepository(SQLiteStore(tmp_path / "assets.sqlite3"), tmp_path / "assets"))
    document = parser.parse(InputManifest(
        project_id="stage07",
        path=Path("tests/fixtures/stage07/clinical_note.txt"),
        source_namespace="note",
    ))

    assert document.status == "success"
    assert len(document.spans) == 4
    assert TextEvidenceValidator().validate_span(document, document.spans[0].locator, document.spans[0].text)

    observations = TextObservationExtractor().extract(document, project_id="stage07", subject_ref="subject_s001")
    by_text = {item.metadata["source_text"]: item for item in observations}

    assert by_text["患者近半年记忆下降。"].value.value is True
    assert by_text["父亲有记忆减退病史。"].metadata["experiencer"] == "family"
    assert by_text["父亲有记忆减退病史。"].value.value is False
    assert by_text["计划下次复查记忆量表。"].metadata["temporal_status"] == "planned"
    assert by_text["计划下次复查记忆量表。"].value.value is False
    assert all(item.validation_status == "needs_review" for item in observations)


def test_knowledge_exact_retrieval_returns_versioned_source_and_rule_candidate() -> None:
    document = KnowledgeDocumentLoader().load_markdown(
        Path("configs/knowledge/xx-v1-data-dictionary.md"),
        document_id="xx_v1_dictionary",
        version="2026-09-07",
    )
    hits = ExactRetriever(KnowledgeIndex.from_documents([document])).search("xx-v1 total scoring")
    candidates = RuleCandidateBuilder().from_hits("xx-v1 total scoring", hits)

    assert hits
    assert hits[0].chunk.document_id == "xx_v1_dictionary"
    assert hits[0].chunk.document_version == "2026-09-07"
    assert candidates
    assert candidates[0].status == "candidate"
    assert candidates[0].chunk_refs == [hits[0].chunk.chunk_id]


def test_multimodal_goal_registers_optional_modal_tasks() -> None:
    request = AnalysisRequest(project_id="stage07", goal="multimodal_summary", as_of=datetime.now(timezone.utc))
    capabilities = CapabilityRegistry.from_directory(Path("configs/capabilities"))
    plan = TemplatePlanner().plan(
        request,
        {spec.capability_id for spec in capabilities.available_for_production()},
        {"xx_v1.total"},
    )
    task_ids = {task.task_id for task in plan.tasks}

    assert {"text_observations", "knowledge_candidates", "diamond_compatibility", "synthesis_report"} <= task_ids
    synthesis = next(task for task in plan.tasks if task.task_id == "synthesis_report")
    assert {dep.task_id for dep in synthesis.depends_on} >= {"text_observations", "knowledge_candidates", "diamond_compatibility"}
    assert PlanValidator(capabilities).validate(request, plan).valid
