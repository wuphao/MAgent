from __future__ import annotations

from pathlib import Path

from multi_agent.application.adapt_cli import run_adaptation
from multi_agent.mapping.operators import parse_number, validate_join_cardinality


FIXTURES = Path("tests/fixtures/schema_variants")
MAPPINGS = Path("configs/mappings")


def test_missing_zero_and_comparator_are_distinct(tmp_path) -> None:
    result = run_adaptation(
        input_path=FIXTURES / "xx_v1_missing_and_compare.csv",
        mapping_path=MAPPINGS / "xx_v1_csv_long.json",
        project_id="stage02",
        source_namespace="csv-long",
        data_dir=tmp_path,
    )
    values = {item["concept_id"]: item["value"] for item in result["projection"]}

    assert values["xx_v1.item_1"]["value"] == 0
    assert values["xx_v1.item_1"]["value_type"] == "number"
    assert values["xx_v1.item_2"]["value_type"] == "missing"
    assert values["xx_v1.item_2"]["missing_reason"] == "source_marker:未测"
    assert values["xx_v1.item_3"]["value"] == 5
    assert values["xx_v1.item_3"]["comparator"] == "<"


def test_same_display_name_in_different_sources_is_not_merged(tmp_path) -> None:
    first = run_adaptation(
        input_path=FIXTURES / "same_name_a.csv",
        mapping_path=MAPPINGS / "xx_v1_csv_long.json",
        project_id="stage02",
        source_namespace="source-a",
        data_dir=tmp_path / "a",
    )
    second = run_adaptation(
        input_path=FIXTURES / "same_name_b.csv",
        mapping_path=MAPPINGS / "xx_v1_csv_long.json",
        project_id="stage02",
        source_namespace="source-b",
        data_dir=tmp_path / "b",
    )

    assert first["projection"][0]["subject_ref"] != second["projection"][0]["subject_ref"]


def test_join_cardinality_violation_is_reported() -> None:
    left = [{"id": "A"}, {"id": "A"}]
    right = [{"id": "A"}]

    failures = validate_join_cardinality(left, right, "id", "id", "one_to_one")

    assert failures == [{"code": "JOIN_CARDINALITY_VIOLATION", "side": "left", "key": "A"}]


def test_bad_number_is_conversion_failure() -> None:
    result = parse_number("not-a-number")

    assert result.value is None
    assert result.error_code == "CONVERSION_FAILED"
