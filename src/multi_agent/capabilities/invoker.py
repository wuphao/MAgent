from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable

from multi_agent.domain.capabilities import CapabilitySpec, ToolArtifact, ToolResult
from multi_agent.domain.observations import ObservationRef


class CapabilityInvoker:
    def __init__(self, specs: dict[str, CapabilitySpec]):
        self.specs = specs

    def invoke(
        self,
        capability_id: str,
        input_refs: list[ObservationRef],
        action: Callable[[], dict],
    ) -> ToolResult:
        spec = self.specs.get(capability_id)
        if spec is None:
            return ToolResult(status="unavailable", error_code="CAPABILITY_NOT_REGISTERED", message=capability_id)
        if spec.availability != "active":
            return ToolResult(status="unavailable", error_code="CAPABILITY_NOT_ACTIVE", message=spec.availability)
        started = datetime.now(timezone.utc)
        started_tick = time.perf_counter()
        try:
            output = action()
        except ValueError as exc:
            return ToolResult(status="not_applicable", error_code=type(exc).__name__, message=str(exc))
        except Exception as exc:
            return ToolResult(status="technical_failure", error_code=type(exc).__name__, message=str(exc))
        finished = datetime.now(timezone.utc)
        artifact = ToolArtifact(
            artifact_id=f"artifact_{capability_id}_{int(started_tick * 1000000)}",
            capability_id=capability_id,
            capability_version=spec.version,
            status="success",
            input_refs=input_refs,
            output=output,
            started_at=started,
            finished_at=finished,
            duration_ms=max(0, int((time.perf_counter() - started_tick) * 1000)),
            limitations=output.get("limitations", []),
        )
        return ToolResult(status="success", artifact=artifact)
