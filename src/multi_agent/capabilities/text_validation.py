from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Iterable

from multi_agent.domain.assets import SourceLocator
from multi_agent.domain.observations import Observation, TypedValue
from multi_agent.ingestion.parsers.text import TextDocument, TextSpan


NEGATION_CUES = ("无", "未见", "否认", "没有", "no ", "denies")
FAMILY_CUES = ("父亲", "母亲", "家族", "哥哥", "姐姐", "brother", "sister", "mother", "father", "family")
FUTURE_CUES = ("计划", "拟", "将", "建议", "复查", "will", "plan")
MEMORY_CUES = ("记忆", "遗忘", "memory", "forget")


class TextEvidenceValidator:
    def validate_span(self, document: TextDocument, locator: SourceLocator, expected_text: str) -> bool:
        page = locator.extensions.get("page")
        start = locator.extensions.get("char_start")
        end = locator.extensions.get("char_end")
        if not isinstance(page, int) or not isinstance(start, int) or not isinstance(end, int):
            return False
        return any(span.page == page and span.char_start == start and span.char_end == end and span.text == expected_text for span in document.spans)


class TextObservationExtractor:
    version = "stage07-text-extractor/1"

    def extract(self, document: TextDocument, project_id: str, subject_ref: str = "subject_text") -> list[Observation]:
        observations: list[Observation] = []
        if document.status != "success":
            return observations
        for span in document.spans:
            lowered = span.text.lower()
            if not any(cue in lowered or cue in span.text for cue in MEMORY_CUES):
                continue
            negated = any(cue in lowered or cue in span.text for cue in NEGATION_CUES)
            experiencer = "family" if any(cue in lowered or cue in span.text for cue in FAMILY_CUES) else "patient"
            temporal_status = "planned" if any(cue in lowered or cue in span.text for cue in FUTURE_CUES) else "observed"
            concept_id = "text.symptom.memory_decline"
            if experiencer == "family":
                concept_id = "text.family_history.memory_decline"
            value = not negated and temporal_status == "observed" and experiencer == "patient"
            observations.append(
                Observation(
                    project_id=project_id,
                    observation_id=_stable_id("observation_text", document.asset_id, str(span.page), str(span.char_start), concept_id),
                    revision=1,
                    subject_ref=subject_ref,
                    concept_id=concept_id,
                    value=TypedValue(value_type="boolean", value=value),
                    event_time=None,
                    event_time_precision="unknown",
                    available_at=datetime.now(timezone.utc),
                    source=span.locator,
                    validation_status="needs_review",
                    idempotency_key=_stable_id("text_extract", project_id, document.asset_id, str(document.asset_revision), str(span.page), str(span.char_start), concept_id),
                    mapping_revision=self.version,
                    metadata={
                        "extraction_method": self.version,
                        "semantic_review_status": "pending",
                        "negated": negated,
                        "experiencer": experiencer,
                        "temporal_status": temporal_status,
                        "source_text": span.text,
                    },
                )
            )
        return observations


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"
