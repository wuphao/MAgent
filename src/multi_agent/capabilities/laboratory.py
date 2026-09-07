from __future__ import annotations

from multi_agent.domain.observations import Observation


class LaboratoryGeneticsCapabilities:
    def summarize_measurements(self, observations: list[Observation]) -> dict:
        measurements = []
        for item in observations:
            if not item.concept_id.startswith(("lab.", "genetic.")):
                continue
            measurements.append(
                {
                    "concept_id": item.concept_id,
                    "value": item.value.model_dump(mode="json"),
                    "event_time": item.event_time,
                    "source": item.source.model_dump(mode="json"),
                }
            )
        return {
            "status": "descriptive_only" if measurements else "no_data",
            "measurements": measurements,
            "limitations": ["no reference rule is applied without platform and method metadata"],
        }
