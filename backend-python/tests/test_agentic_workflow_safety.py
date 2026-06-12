from decimal import Decimal
from types import SimpleNamespace

from app.schemas.result import TaskFinalResult
from app.services.orchestration_service import OrchestrationService
from app.utils.text_utils import MANUAL_REVIEW_STRATEGY


def _payload(*, constraints: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        task_id=901,
        strategy_goal="MAX_PROFIT",
        constraints=constraints or {"min_profit_rate": 0.2, "max_discount_rate": 0.5},
        product=SimpleNamespace(
            current_price=Decimal("120.00"),
            cost_price=Decimal("80.00"),
        ),
        baseline_sales=100,
        baseline_profit=Decimal("500.00"),
    )


def _manager_output(final_price: str = "105.00") -> dict:
    return {
        "finalPrice": final_price,
        "expectedSales": 100,
        "expectedProfit": "2500.00",
        "profitGrowth": "2000.00",
        "executeStrategy": MANUAL_REVIEW_STRATEGY,
        "isPass": True,
        "thinking": "manager-thinking",
        "resultSummary": "可确认：按利润优先处理，建议应用该价格。",
        "suggestedMinPrice": "90.00",
        "suggestedMaxPrice": "130.00",
        "arbitrationDecision": "FAST_PATH",
        "arbitrationReason": "all signals aligned",
    }


def _service_with_capture() -> tuple[OrchestrationService, list[TaskFinalResult]]:
    service = OrchestrationService.__new__(OrchestrationService)
    captured: list[TaskFinalResult] = []
    service.result_tool = SimpleNamespace(write_final_result=captured.append)
    service.progress_service = SimpleNamespace(publish_sync=lambda *args, **kwargs: None)
    service.execution_id = "exec-test"
    return service, captured


def test_finalize_result_routes_price_below_cost_to_manual_review():
    service, captured = _service_with_capture()

    result = service._finalize_result(_payload(), _manager_output(final_price="75.00"))

    assert result.is_pass is False
    assert result.execute_strategy == MANUAL_REVIEW_STRATEGY
    assert captured == [result]


def test_finalize_result_routes_non_improving_profit_to_manual_review():
    service, _captured = _service_with_capture()
    manager_output = _manager_output(final_price="110.00")
    manager_output["expectedProfit"] = "500.00"

    result = service._finalize_result(_payload(), manager_output)

    assert result.is_pass is False
    assert result.execute_strategy == MANUAL_REVIEW_STRATEGY


def test_finalize_result_keeps_existing_final_result_contract_fields_only():
    field_aliases = set(TaskFinalResult.model_json_schema(by_alias=True)["properties"])

    assert field_aliases == {
        "taskId",
        "finalPrice",
        "expectedSales",
        "expectedProfit",
        "profitGrowth",
        "isPass",
        "executeStrategy",
        "resultSummary",
        "suggestedMinPrice",
        "suggestedMaxPrice",
    }
