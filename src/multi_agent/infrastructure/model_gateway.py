from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Protocol


class ModelGatewayError(RuntimeError):
    pass


class ModelGateway(Protocol):
    def chat_structured(
        self,
        messages: list[dict[str, str]],
        schema_name: str,
        budget_context: "BudgetContext | None" = None,
    ) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class BudgetContext:
    run_id: str
    task_id: str
    reserved_tokens: int
    prompt_version: str


class FakeModelGateway:
    def __init__(self, responses: list[dict[str, Any] | Exception]):
        self._responses = deque(responses)
        self.calls: list[dict[str, Any]] = []

    def chat_structured(
        self,
        messages: list[dict[str, str]],
        schema_name: str,
        budget_context: BudgetContext | None = None,
    ) -> dict[str, Any]:
        self.calls.append({"messages": messages, "schema_name": schema_name})
        if not self._responses:
            raise ModelGatewayError("fake gateway has no queued response")
        response = self._responses.popleft()
        if isinstance(response, Exception):
            raise response
        return response


class DeepSeekModelGateway:
    def __init__(self):
        from llm_client import DeepSeekClient

        self.client = DeepSeekClient()

    def chat_structured(
        self,
        messages: list[dict[str, str]],
        schema_name: str,
        budget_context: BudgetContext | None = None,
    ) -> dict[str, Any]:
        result = self.client.chat_json(messages, temperature=0.0, num_predict=1600)
        if not isinstance(result, dict):
            raise ModelGatewayError(f"{schema_name} response is not an object")
        return result
