import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.schemas.result import TaskFinalResult
from app.services.orchestration_service import OrchestrationService
from app.tools.risk_rule_tool import RiskRuleTool
from app.utils.text_utils import MANUAL_REVIEW_STRATEGY


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "agentic_workflow"
CASE_FILES = sorted(FIXTURE_DIR.glob("*.json"))


def _payload(case: dict) -> SimpleNamespace:
    payload = case["payload"]
    return SimpleNamespace(
        task_id=1001,
        strategy_goal=payload["strategyGoal"],
        constraints=payload["constraints"],
        product=SimpleNamespace(
            current_price=Decimal(payload["currentPrice"]),
            cost_price=Decimal(payload["costPrice"]),
        ),
        baseline_sales=int(payload["baselineSales"]),
        baseline_profit=Decimal(payload["baselineProfit"]),
    )


def _manager_output(case: dict) -> dict:
    output = dict(case["managerOutput"])
    output.setdefault("executeStrategy", MANUAL_REVIEW_STRATEGY)
    output.setdefault("thinking", "manager-thinking")
    output.setdefault("suggestedMinPrice", "90.00")
    output.setdefault("suggestedMaxPrice", "150.00")
    output.setdefault("selectedAgent", "DATA_ANALYSIS")
    output.setdefault("selectedPrice", output["finalPrice"])
    return output


def _service_with_capture() -> tuple[OrchestrationService, list[TaskFinalResult]]:
    service = OrchestrationService.__new__(OrchestrationService)
    captured: list[TaskFinalResult] = []
    service.result_tool = SimpleNamespace(write_final_result=captured.append)
    service.progress_service = SimpleNamespace(publish_sync=lambda *args, **kwargs: None)
    service.execution_id = "exec-business"
    return service, captured


def _load_case(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case_path", CASE_FILES, ids=[path.stem for path in CASE_FILES])
def test_agentic_workflow_business_case_outputs(case_path: Path):
    case = _load_case(case_path)
    payload = _payload(case)
    manager_output = _manager_output(case)
    expected = case["expected"]
    service, captured = _service_with_capture()

    result = service._finalize_result(payload, manager_output)

    assert captured == [result]
    assert str(result.final_price) == expected["finalPrice"]
    assert str(result.expected_profit) == expected["expectedProfit"]
    assert str(result.profit_growth) == expected["profitGrowth"]
    assert result.is_pass is expected["isPass"]
    if "summaryStartsWith" in expected:
        assert result.result_summary.startswith(expected["summaryStartsWith"])
    if "summaryContains" in expected:
        assert expected["summaryContains"] in result.result_summary
    assert manager_output["arbitrationReason"]
    assert manager_output["arbitrationDecision"] == expected["arbitrationDecision"]
    assert manager_output["toolAudit"] == expected["toolAudit"]


@pytest.mark.parametrize("case_path", CASE_FILES, ids=[path.stem for path in CASE_FILES])
def test_agentic_workflow_business_case_hard_assertions(case_path: Path):
    case = _load_case(case_path)
    payload = _payload(case)
    manager_output = _manager_output(case)
    summary = manager_output["resultSummary"]
    decision = manager_output["arbitrationDecision"]
    tool_audit = manager_output["toolAudit"]
    risk = RiskRuleTool().evaluate(
        current_price=payload.product.current_price,
        cost_price=payload.product.cost_price,
        candidate_price=Decimal(manager_output["finalPrice"]),
        constraints=payload.constraints,
    )

    if Decimal(manager_output["finalPrice"]) < Decimal(risk["safe_floor_price"]):
        assert not summary.startswith("可确认")
    if Decimal(manager_output["expectedProfit"]) <= payload.baseline_profit and payload.strategy_goal != "CLEARANCE":
        assert not summary.startswith("可确认")
    if decision == "MARKET_WEAK_SIGNAL":
        assert "强跟" in manager_output["arbitrationReason"]
    if any(item.get("status") in {"error", "timeout"} for item in tool_audit):
        assert summary.startswith(("建议复核", "不建议确认"))
    assert "下一步" in summary
    assert "风险结论" in summary
