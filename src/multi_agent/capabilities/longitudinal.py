from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Iterable

from multi_agent.capabilities.invoker import CapabilityInvoker
from multi_agent.domain.capabilities import ToolResult
from multi_agent.domain.observations import Observation, ObservationRef


class LongitudinalCapabilities:
    def __init__(self, invoker: CapabilityInvoker):
        self.invoker = invoker

    def describe(self, observations: Iterable[Observation], concept_id: str) -> ToolResult:
        observation_list = [item for item in observations if item.concept_id == concept_id]
        refs = [ObservationRef(observation_id=item.observation_id, revision=item.revision) for item in observation_list]

        def action() -> dict:
            return describe_series(observation_list, concept_id)

        return self.invoker.invoke("longitudinal_describe", refs, action)


def describe_series(observations: list[Observation], concept_id: str) -> dict:
    comparable = [
        item for item in observations
        if item.value.value_type == "number" and item.event_time and item.event_time_precision == "date"
    ]
    if not comparable:
        return {"concept_id": concept_id, "status": "no_data", "n_observations": len(observations), "series": []}
    grouped = defaultdict(list)
    for item in comparable:
        grouped[(item.subject_ref, item.mapping_revision, item.value.unit)].append(item)
    summaries = []
    for (subject_ref, mapping_revision, unit), items in grouped.items():
        items = sorted(items, key=lambda item: (item.event_time or "", item.source.record_locator))
        distinct_dates = {_parse_date(item.event_time) for item in items}
        status = "analyzed"
        delta = None
        if len(distinct_dates) < 2:
            status = "insufficient_points"
        else:
            delta = items[-1].value.value - items[0].value.value
        summaries.append(
            {
                "subject_ref": subject_ref,
                "concept_id": concept_id,
                "mapping_revision": mapping_revision,
                "unit": unit,
                "status": status,
                "n_observations": len(items),
                "n_distinct_dates": len(distinct_dates),
                "first": {"date": items[0].event_time, "value": items[0].value.value},
                "last": {"date": items[-1].event_time, "value": items[-1].value.value},
                "delta": delta,
                "series": [
                    {
                        "date": item.event_time,
                        "value": item.value.value,
                        "record_locator": item.source.record_locator,
                        "record_key": item.metadata.get("record_key"),
                    }
                    for item in items
                ],
            }
        )
    return {"concept_id": concept_id, "groups": summaries}


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(value)
