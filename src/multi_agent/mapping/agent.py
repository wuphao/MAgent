from __future__ import annotations

import hashlib
from typing import Any

from pydantic import ValidationError

from multi_agent.domain.mapping import SourceProfile
from multi_agent.infrastructure.model_gateway import ModelGateway, ModelGatewayError
from multi_agent.mapping.candidate import BindingRationale, MappingCandidate, MetadataQuestion
from multi_agent.mapping.prompts import PROMPT_VERSION, SYSTEM_PROMPT
from multi_agent.mapping.spec import MappingSpec


ALLOWED_TRANSFORMS = {"parse_number", "parse_string"}


class MappingCandidateAgent:
    def __init__(
        self,
        gateway: ModelGateway,
        registered_concepts: set[str],
        max_repairs: int = 2,
        model_name: str = "fake",
    ):
        self.gateway = gateway
        self.registered_concepts = registered_concepts
        self.max_repairs = max_repairs
        self.model_name = model_name

    def propose(self, profile: SourceProfile, source_dictionary: dict[str, Any] | None = None) -> MappingCandidate:
        diagnostics: list[dict[str, Any]] = []
        messages = self._messages(profile, source_dictionary or {}, diagnostics)
        for attempt in range(self.max_repairs + 1):
            try:
                response = self.gateway.chat_structured(messages, "MappingCandidate")
            except ModelGatewayError as exc:
                diagnostics.append({"code": "MODEL_GATEWAY_ERROR", "message": str(exc), "attempt": attempt})
                break
            candidate = self._candidate_from_response(response, diagnostics)
            if candidate.status in {"proposed", "needs_metadata"}:
                return candidate
            messages = self._messages(profile, source_dictionary or {}, diagnostics)
        return MappingCandidate(
            candidate_id=_stable_id("candidate", profile.structure_fingerprint, "invalid"),
            status="invalid",
            spec=None,
            diagnostics=diagnostics,
            model_name=self.model_name,
            prompt_version=PROMPT_VERSION,
        )

    def _candidate_from_response(
        self,
        response: dict[str, Any],
        diagnostics: list[dict[str, Any]],
    ) -> MappingCandidate:
        questions = [MetadataQuestion.model_validate(item) for item in response.get("questions", [])]
        if questions and response.get("spec") is None:
            return MappingCandidate(
                candidate_id=_stable_id("candidate", str(response)),
                status="needs_metadata",
                questions=questions,
                diagnostics=diagnostics,
                model_name=self.model_name,
                prompt_version=PROMPT_VERSION,
            )
        try:
            spec = MappingSpec.model_validate(response.get("spec"))
        except ValidationError as exc:
            diagnostics.append({"code": "INVALID_SPEC_SCHEMA", "errors": exc.errors()})
            return _invalid_candidate(diagnostics, self.model_name)
        unknown_transforms = [
            binding.transform for binding in spec.bindings if binding.transform not in ALLOWED_TRANSFORMS
        ]
        if unknown_transforms:
            diagnostics.append({"code": "UNKNOWN_OPERATOR", "operators": sorted(set(unknown_transforms))})
            return _invalid_candidate(diagnostics, self.model_name)
        unknown_concepts = [
            binding.concept_id
            for binding in spec.bindings
            if binding.concept_id != "from_field" and binding.concept_id not in self.registered_concepts
        ]
        if unknown_concepts:
            diagnostics.append({"code": "UNKNOWN_CONCEPT", "concepts": sorted(set(unknown_concepts))})
            return _invalid_candidate(diagnostics, self.model_name)
        rationales = [
            BindingRationale.model_validate(item)
            for item in response.get("rationales", [])
        ]
        return MappingCandidate(
            candidate_id=_stable_id("candidate", spec.mapping_id, spec.version),
            status="proposed",
            spec=spec,
            rationales=rationales,
            questions=questions,
            diagnostics=diagnostics,
            model_name=self.model_name,
            prompt_version=PROMPT_VERSION,
        )

    def _messages(
        self,
        profile: SourceProfile,
        source_dictionary: dict[str, Any],
        diagnostics: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        payload = {
            "profile": profile.model_dump(mode="json"),
            "source_dictionary": source_dictionary,
            "registered_concepts": sorted(self.registered_concepts),
            "allowed_transforms": sorted(ALLOWED_TRANSFORMS),
            "previous_diagnostics": diagnostics,
        }
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": str(payload)},
        ]


def _invalid_candidate(diagnostics: list[dict[str, Any]], model_name: str) -> MappingCandidate:
    return MappingCandidate(
        candidate_id=_stable_id("candidate", str(diagnostics)),
        status="invalid",
        spec=None,
        diagnostics=diagnostics,
        model_name=model_name,
        prompt_version=PROMPT_VERSION,
    )


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"
