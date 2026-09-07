from __future__ import annotations

from datetime import datetime, timezone

from multi_agent.agents.base import TaskContext
from multi_agent.agents.longitudinal import LongitudinalAgent
from multi_agent.capabilities.invoker import CapabilityInvoker
from multi_agent.capabilities.quality import QualityService
from multi_agent.domain.assets import SourceLocator
from multi_agent.domain.capabilities import CapabilitySpec
from multi_agent.domain.observations import Observation, TypedValue


def _obs(
    observation_id: str,
    value: int,
    event_time: str | None,
    *,
    locator: str = "$.x",
    precision: str = "date",
    revision: str = "mapping/1",
) -> Observation:
    return Observation(
        project_id="stage04",
        observation_id=observation_id,
        subject_ref="subject1",
        concept_id="xx_v1.total",
        value=TypedValue(value_type="number", value=value, comparator="="),
        event_time=event_time,
        event_time_precision=precision,
        available_at=datetime.now(timezone.utc),
        source=SourceLocator(
            asset_id="asset1",
            asset_revision=1,
            record_locator=locator,
            value_locator=f"{locator}.total",
            parser_version="test/1",
        ),
        idempotency_key=observation_id,
        mapping_revision=revision,
    )


def _invoker() -> CapabilityInvoker:
    return CapabilityInvoker(
        {
            "longitudinal_describe": CapabilitySpec(
                capability_id="longitudinal_describe",
                version="longitudinal_describe/1",
                input_schema="series",
                output_schema="summary",
            )
        }
    )


def test_longitudinal_sorts_dates_and_reports_delta() -> None:
    context = TaskContext(
        project_id="stage04",
        goal="longitudinal_xx_v1",
        observations=[_obs("late", 6, "2024-07-01"), _obs("early", 4, "2024-01-01")],
    )

    result = LongitudinalAgent().execute(context, _invoker())

    assert result.status == "success"
    assert "changed by 2" in result.findings[0].proposition


def test_longitudinal_same_day_is_insufficient_not_no_decline() -> None:
    context = TaskContext(
        project_id="stage04",
        goal="longitudinal_xx_v1",
        observations=[_obs("a", 4, "2024-01-01", locator="$.a"), _obs("b", 6, "2024-01-01", locator="$.b")],
    )

    result = LongitudinalAgent().execute(context, _invoker())

    assert result.status == "insufficient_points"
    assert "insufficient distinct dates" in result.findings[0].proposition


def test_longitudinal_month_precision_is_insufficient_dates() -> None:
    context = TaskContext(
        project_id="stage04",
        goal="longitudinal_xx_v1",
        observations=[_obs("month", 4, "2024-01", precision="month")],
    )

    result = LongitudinalAgent().execute(context, _invoker())

    assert result.status == "no_data"


def test_quality_goal_does_not_fail_for_missing_unrelated_imaging() -> None:
    observations = [_obs("total", 4, "2024-01-01")]

    quality = QualityService().check_goal("longitudinal_xx_v1", observations)

    assert quality["status"] == "pass"
    assert "imaging" not in quality["missing_concepts"]
