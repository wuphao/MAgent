from __future__ import annotations

from multi_agent.infrastructure.model_gateway import BudgetContext, FakeModelGateway, ModelGatewayError
from multi_agent.storage.tasks import BudgetLedger, TaskStore


def test_budget_reservation_is_hard_limit(tmp_path) -> None:
    ledger = BudgetLedger(TaskStore(tmp_path / "tasks.sqlite3"), "run1", max_calls=1, max_tokens=10)

    first = ledger.reserve("r1", "task1", calls=1, tokens=6)
    second = ledger.reserve("r2", "task2", calls=1, tokens=6)

    assert first is True
    assert second is False
    assert len(ledger.entries()) == 1


def test_budget_settlement_can_mark_usage_unknown(tmp_path) -> None:
    ledger = BudgetLedger(TaskStore(tmp_path / "tasks.sqlite3"), "run1", max_calls=2, max_tokens=100)

    ledger.reserve("r1", "model_task", calls=1, tokens=50)
    ledger.settle("s1", "model_task", calls=1, tokens=0, usage_unknown=True, note="response lost after provider accepted request")

    entries = ledger.entries()
    assert entries[-1]["usage_unknown"] == 1
    assert entries[-1]["cost"] is None


def test_fake_gateway_records_budget_context() -> None:
    gateway = FakeModelGateway([{"ok": True}])
    context = BudgetContext(run_id="run1", task_id="model_task", reserved_tokens=50, prompt_version="prompt/1")

    result = gateway.chat_structured([{"role": "user", "content": "x"}], "Schema", budget_context=context)

    assert result == {"ok": True}
    assert gateway.calls[0]["schema_name"] == "Schema"


def test_fake_gateway_can_simulate_timeout() -> None:
    gateway = FakeModelGateway([ModelGatewayError("timeout")])

    try:
        gateway.chat_structured([], "Schema")
    except ModelGatewayError as exc:
        assert "timeout" in str(exc)
        return
    raise AssertionError("expected timeout simulation")
