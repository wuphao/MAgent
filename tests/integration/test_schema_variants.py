from __future__ import annotations

import json
from pathlib import Path

from multi_agent.application.adapt_cli import run_adaptation


FIXTURES = Path("tests/fixtures/schema_variants")
MAPPINGS = Path("configs/mappings")


def _simple_projection(result: dict) -> list[dict]:
    return [
        {
            "source_subject_key": item["source_subject_key"],
            "record_key": item["record_key"],
            "event_time": item["event_time"],
            "concept_id": item["concept_id"],
            "value": item["value"]["value"],
        }
        for item in result["projection"]
    ]


def test_four_layouts_project_to_same_semantics(tmp_path) -> None:
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))["projection"]
    cases = [
        ("xx_v1_legacy_rwe.json", "xx_v1_legacy_json.json", "legacy-json"),
        ("xx_v1_csv_long.csv", "xx_v1_csv_long.json", "csv-long"),
        ("xx_v1_wide.xlsx", "xx_v1_xlsx_wide.json", "xlsx-wide"),
        ("xx_v1_nested.json", "xx_v1_nested_json.json", "nested-json"),
    ]

    for filename, mapping, namespace in cases:
        result = run_adaptation(
            input_path=FIXTURES / filename,
            mapping_path=MAPPINGS / mapping,
            project_id="stage02",
            source_namespace=namespace,
            data_dir=tmp_path / namespace,
        )

        assert result["validation"]["status"] == "valid"
        assert result["validation"]["published_count"] == 10
        assert _simple_projection(result) == expected
        assert "remark" in result["validation"]["unmapped_fields"]


def test_csv_line_numbers_are_original_file_lines(tmp_path) -> None:
    result = run_adaptation(
        input_path=FIXTURES / "xx_v1_csv_long.csv",
        mapping_path=MAPPINGS / "xx_v1_csv_long.json",
        project_id="stage02",
        source_namespace="csv-long",
        data_dir=tmp_path,
    )

    assert result["validation"]["source_locators_checked"] == 10
    # First data row is physical file line 2 because line 1 is the header.
    first_locator = result["projection"][0]["record_key"]
    assert first_locator == "XX-S001-2024-01-01-A"


def test_nested_records_keep_same_day_record_identity(tmp_path) -> None:
    result = run_adaptation(
        input_path=FIXTURES / "xx_v1_nested.json",
        mapping_path=MAPPINGS / "xx_v1_nested_json.json",
        project_id="stage02",
        source_namespace="nested-json",
        data_dir=tmp_path,
    )

    keys = {item["record_key"] for item in result["projection"]}
    assert keys == {"XX-S001-2024-01-01-A", "XX-S001-2024-07-01-A"}
