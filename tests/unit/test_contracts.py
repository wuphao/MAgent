from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from multi_agent.domain.assets import SourceLocator
from multi_agent.domain.errors import format_validation_errors
from multi_agent.domain.observations import Observation, SubjectLink, TypedValue


def test_zero_is_a_concrete_number_not_missing() -> None:
    value = TypedValue(value_type="number", value=0, comparator="=")

    assert value.value == 0
    assert value.missing_reason is None


def test_missing_requires_reason_and_no_value() -> None:
    with pytest.raises(ValidationError) as exc:
        TypedValue(value_type="missing", value=0)

    errors = format_validation_errors(exc.value)
    assert errors[0]["code"] == "value_error"
    assert errors[0]["field_path"] == "$"


def test_unknown_subject_is_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        SubjectLink(
            project_id="p1",
            source_namespace="source_a",
            source_subject_key="raw-1",
            subject_ref="unknown",
            basis=["missing source identifier"],
        )

    assert format_validation_errors(exc.value)[0]["field_path"] == "subject_ref"


def test_source_locator_requires_record_and_value_position() -> None:
    with pytest.raises(ValidationError) as exc:
        SourceLocator(
            asset_id="asset_a",
            asset_revision=1,
            record_locator="unknown",
            value_locator="$.score",
            parser_version="parser/1",
        )

    assert format_validation_errors(exc.value)[0]["code"] == "value_error"


def test_observation_requires_consistent_time_precision() -> None:
    with pytest.raises(ValidationError) as exc:
        Observation(
            project_id="p1",
            observation_id="obs1",
            subject_ref="subject1",
            concept_id="xx.total",
            value=TypedValue(value_type="number", value=4, comparator="="),
            event_time=None,
            event_time_precision="date",
            available_at=datetime.now(timezone.utc),
            source=SourceLocator(
                asset_id="asset_a",
                asset_revision=1,
                record_locator="$.xx_v1[0]",
                value_locator="$.xx_v1[0].total",
                parser_version="parser/1",
            ),
            idempotency_key="asset:record:xx.total:mapping",
            mapping_revision="mapping/1",
        )

    assert format_validation_errors(exc.value)[0]["field_path"] == "$"
