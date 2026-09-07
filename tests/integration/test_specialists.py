from __future__ import annotations

from pathlib import Path

from multi_agent.application.adapt_cli import run_adaptation
from multi_agent.application.specialist_cli import run_specialists
from multi_agent.capabilities.invoker import CapabilityInvoker
from multi_agent.domain.capabilities import CapabilitySpec
from multi_agent.registries.capabilities import CapabilityRegistry


FIXTURES = Path("tests/fixtures/schema_variants")
MAPPINGS = Path("configs/mappings")


def _adapt(input_file: str, mapping_file: str, namespace: str, tmp_path: Path) -> Path:
    data_dir = tmp_path / namespace
    run_adaptation(
        input_path=FIXTURES / input_file,
        mapping_path=MAPPINGS / mapping_file,
        project_id="stage04",
        source_namespace=namespace,
        data_dir=data_dir,
    )
    return data_dir / "stage02.sqlite3"


def _assessment_results(output: dict) -> list[dict]:
    assessment = next(item for item in output["agent_results"] if item["agent_name"] == "AssessmentAgent")
    artifact = assessment["output"]["artifact"]
    return artifact["output"]["results"]


def test_assessment_agent_scores_four_layouts_the_same(tmp_path) -> None:
    cases = [
        ("xx_v1_legacy_rwe.json", "xx_v1_legacy_json.json", "legacy-json"),
        ("xx_v1_csv_long.csv", "xx_v1_csv_long.json", "csv-long"),
        ("xx_v1_wide.xlsx", "xx_v1_xlsx_wide.json", "xlsx-wide"),
        ("xx_v1_nested.json", "xx_v1_nested_json.json", "nested-json"),
    ]
    expected = [
        ("2024-01-01", 4, 4, 0),
        ("2024-07-01", 6, 6, 0),
    ]

    for input_file, mapping_file, namespace in cases:
        db = _adapt(input_file, mapping_file, namespace, tmp_path)
        output = run_specialists(db, "stage04", "xx_v1_assessment", Path("configs/instruments"), Path("configs/capabilities"))
        results = [
            (item["event_time"], item["computed_total"], item["reported_total"], item["difference"])
            for item in _assessment_results(output)
        ]

        assert results == expected


def test_capability_registry_excludes_demo_from_production(tmp_path) -> None:
    config = tmp_path / "demo.json"
    config.write_text(
        """{
  "capability_id": "demo_only",
  "version": "demo_only/1",
  "availability": "demo",
  "input_schema": "x",
  "output_schema": "y"
}""",
        encoding="utf-8",
    )

    registry = CapabilityRegistry.from_directory(tmp_path)

    assert registry.available_for_production() == []


def test_invoker_reports_unavailable_capability() -> None:
    result = CapabilityInvoker({}).invoke("missing", [], lambda: {"unused": True})

    assert result.status == "unavailable"
    assert result.error_code == "CAPABILITY_NOT_REGISTERED"


def test_assessment_detects_reported_score_conflict(tmp_path) -> None:
    db = _adapt("xx_v1_legacy_rwe.json", "xx_v1_legacy_json.json", "legacy-json", tmp_path)
    # Reuse the validated pipeline by changing the source fixture through a separate file.
    conflict = tmp_path / "conflict.json"
    text = (FIXTURES / "xx_v1_legacy_rwe.json").read_text(encoding="utf-8").replace('"total": 4', '"total": 5', 1)
    conflict.write_text(text, encoding="utf-8")
    conflict_db_dir = tmp_path / "conflict"
    run_adaptation(conflict, MAPPINGS / "xx_v1_legacy_json.json", "stage04", "legacy-json", conflict_db_dir)
    output = run_specialists(conflict_db_dir / "stage02.sqlite3", "stage04", "xx_v1_assessment", Path("configs/instruments"), Path("configs/capabilities"))
    assessment = next(item for item in output["agent_results"] if item["agent_name"] == "AssessmentAgent")

    assert any(finding["status"] == "unresolved" and "differs" in finding["proposition"] for finding in assessment["findings"])
