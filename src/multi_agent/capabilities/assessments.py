from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from multi_agent.domain.capabilities import ToolResult
from multi_agent.domain.instruments import InstrumentSpec
from multi_agent.domain.observations import Observation, ObservationRef
from multi_agent.capabilities.invoker import CapabilityInvoker


class AssessmentCapabilities:
    def __init__(self, invoker: CapabilityInvoker):
        self.invoker = invoker

    def score_xx_v1(
        self,
        observations: Iterable[Observation],
        instrument: InstrumentSpec,
    ) -> ToolResult:
        observation_list = list(observations)
        input_refs = [
            ObservationRef(observation_id=item.observation_id, revision=item.revision)
            for item in observation_list
        ]

        def action() -> dict:
            return compute_xx_v1_scores(observation_list, instrument)

        return self.invoker.invoke("xx_v1_score", input_refs, action)


def compute_xx_v1_scores(observations: list[Observation], instrument: InstrumentSpec) -> dict:
    item_concepts = [
        concept for concept, role in instrument.item_roles.items() if role == "item"
    ]
    total_concept = next(
        (concept for concept, role in instrument.item_roles.items() if role == "total"),
        None,
    )
    if not item_concepts:
        raise ValueError("instrument has no registered item concepts")
    records = defaultdict(dict)
    refs = defaultdict(dict)
    for observation in observations:
        if observation.concept_id not in set(item_concepts + ([total_concept] if total_concept else [])):
            continue
        key = (
            observation.subject_ref,
            observation.event_time,
            str(observation.metadata.get("record_key") or observation.source.record_locator),
        )
        records[key][observation.concept_id] = observation.value
        refs[key][observation.concept_id] = {
            "observation_id": observation.observation_id,
            "revision": observation.revision,
        }

    results = []
    for key, values in records.items():
        missing_items = [
            concept for concept in item_concepts
            if concept not in values or values[concept].value_type == "missing"
        ]
        computed_total = None
        status = "scored"
        if missing_items:
            status = "insufficient_items"
        else:
            computed_total = sum(values[concept].value for concept in item_concepts)
        reported = values.get(total_concept) if total_concept else None
        difference = None
        if computed_total is not None and reported and reported.value_type == "number":
            difference = reported.value - computed_total
        results.append(
            {
                "subject_ref": key[0],
                "event_time": key[1],
                "record_locator": key[2],
                "status": status,
                "computed_total": computed_total,
                "reported_total": reported.value if reported else None,
                "difference": difference,
                "item_refs": refs[key],
                "limitations": ["missing item prevents total computation"] if missing_items else [],
            }
        )
    return {
        "instrument": instrument.definition_version,
        "score_kind": "computed_total",
        "record_count": len(results),
        "results": sorted(results, key=lambda item: (item["subject_ref"], item["event_time"] or "", item["record_locator"])),
        "limitations": [] if results else ["no scorable XX-v1 observations"],
    }
