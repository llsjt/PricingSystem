from decimal import Decimal
from types import SimpleNamespace

from app.crew import crew_factory


def _payload() -> SimpleNamespace:
    return SimpleNamespace(
        product=SimpleNamespace(
            product_id=1001,
            product_name="coffee",
            category_name="beverage",
            current_price=Decimal("29.90"),
            cost_price=Decimal("16.80"),
        ),
        strategy_goal="MAX_PROFIT",
        baseline_sales=120,
        baseline_profit=Decimal("1200.00"),
        constraints={
            "min_profit_rate": 0.2,
            "max_discount_rate": 0.4,
            "min_price": 22.0,
            "max_price": 39.0,
            "force_manual_review": True,
        },
        metrics=[],
        traffic=[],
    )


def _capture_tasks(monkeypatch):
    class _FakeTask:
        instances = []

        def __init__(self, **kwargs):  # noqa: ANN003
            self.kwargs = kwargs
            _FakeTask.instances.append(self)

    class _FakeCrew:
        def __init__(self, **kwargs):  # noqa: ANN003
            self.kwargs = kwargs

    monkeypatch.setattr(crew_factory, "_precompute_data_summary", lambda _payload: "data-summary")
    monkeypatch.setattr(crew_factory, "_precompute_data_projection", lambda _payload: "data-projection")
    monkeypatch.setattr(crew_factory, "_precompute_competitor_summary", lambda _payload: "competitor-summary")
    monkeypatch.setattr(crew_factory, "_precompute_risk_projection", lambda _payload: "risk-projection")
    monkeypatch.setattr(crew_factory, "_build_metrics_summary", lambda _payload: "metrics-summary")
    monkeypatch.setattr(crew_factory, "_build_constraints_text", lambda _constraints: "constraints-summary")
    monkeypatch.setattr(
        crew_factory,
        "build_crewai_agents",
        lambda **kwargs: {
            "DATA_ANALYSIS": "data-agent",
            "MARKET_INTEL": "market-agent",
            "RISK_CONTROL": "risk-agent",
            "MANAGER_COORDINATOR": "manager-agent",
        },
    )
    monkeypatch.setattr(crew_factory, "Task", _FakeTask)
    monkeypatch.setattr(crew_factory, "Crew", _FakeCrew)

    crew_factory.build_pricing_crew(_payload(), analysis_llm=object(), manager_llm=object())
    return {task.kwargs["agent"]: task.kwargs for task in _FakeTask.instances}


def test_manager_prompt_contains_fast_and_verification_paths(monkeypatch):
    manager_task = _capture_tasks(monkeypatch)["manager-agent"]

    assert "Fast Path" in manager_task["description"]
    assert "Verification Path" in manager_task["description"]
    assert "FAST_PATH" in manager_task["description"]
    assert "RISK_VERIFICATION" in manager_task["description"]


def test_manager_prompt_binds_complete_risk_parameters(monkeypatch):
    description = _capture_tasks(monkeypatch)["manager-agent"]["description"]

    for field_name in (
        "current_price",
        "cost_price",
        "candidate_price",
        "min_profit_rate",
        "max_discount_rate",
        "min_price",
        "max_price",
        "force_manual_review",
    ):
        assert field_name in description


def test_manager_prompt_forbids_string_null_and_new_schema_fields(monkeypatch):
    manager_task = _capture_tasks(monkeypatch)["manager-agent"]
    description = manager_task["description"]
    expected_output = manager_task["expected_output"]

    assert 'not the string value "null"' in description
    assert '"selectedAgent": "DATA_ANALYSIS/MARKET_INTEL/RISK_CONTROL/null"' not in expected_output
    assert "loopTrace" not in expected_output
    assert "verificationSummary" not in expected_output
    assert "verificationPath" not in expected_output
