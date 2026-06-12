import json
from datetime import date
from decimal import Decimal
from inspect import signature

from app.crew.protocols import CrewRunPayload
from app.application.cancellation_checker import request_shutdown, clear_shutdown, TaskCancelledError
from app.schemas.agent import DailyMetricSnapshot, ProductContext, TrafficSnapshot
from app.tools.crewai_tools import evaluate_risk_rules, query_competitor_summary, summarize_product_data
from app.tools.tool_context import ToolContext, active_tool_context
from app.tools.tool_registry import allowed_tool_names, get_tools_for_agent, is_tool_allowed


def _payload() -> CrewRunPayload:
    product = ProductContext(
        productId=101,
        shopId=9,
        productName="coffee",
        categoryName="beverage",
        currentPrice=Decimal("29.90"),
        costPrice=Decimal("16.80"),
        stock=250,
    )
    metrics = [
        DailyMetricSnapshot(
            statDate=date(2026, 5, 1),
            visitorCount=100,
            addCartCount=12,
            payBuyerCount=8,
            salesCount=10,
            turnover=Decimal("299.00"),
            conversionRate=Decimal("0.0800"),
        ),
        DailyMetricSnapshot(
            statDate=date(2026, 5, 2),
            visitorCount=120,
            addCartCount=15,
            payBuyerCount=10,
            salesCount=12,
            turnover=Decimal("358.80"),
            conversionRate=Decimal("0.0833"),
        ),
    ]
    traffic = [
        TrafficSnapshot(
            statDate=date(2026, 5, 1),
            trafficSource="search",
            impressionCount=1000,
            clickCount=80,
            visitorCount=75,
            payAmount=Decimal("299.00"),
            roi=Decimal("2.5"),
        )
    ]
    return CrewRunPayload(
        task_id=55,
        strategy_goal="稳健提价",
        constraints={"min_profit_rate": 0.15},
        product=product,
        metrics=metrics,
        traffic=traffic,
        baseline_sales=120,
        baseline_profit=Decimal("1572.00"),
    )


def _json_from_tool(tool) -> dict:
    return json.loads(tool.func())


def test_tool_context_default_is_none():
    assert active_tool_context.get() is None


def test_query_competitor_summary_has_no_arguments_schema():
    assert list(signature(query_competitor_summary.func).parameters) == []
    assert query_competitor_summary.args_schema.model_json_schema()["properties"] == {}


def test_query_competitor_summary_uses_precomputed_context():
    ctx = ToolContext(
        payload=_payload(),
        task_id=55,
        execution_id="exec-1",
        agent_code="MARKET_INTEL",
        precomputed_competitor_summary="竞品价格集中在 26-32 元",
    )
    token = active_tool_context.set(ctx)
    try:
        result = _json_from_tool(query_competitor_summary)
    finally:
        active_tool_context.reset(token)

    assert result == {
        "ok": True,
        "data": {"summary": "竞品价格集中在 26-32 元"},
        "errorType": None,
        "errorMessage": None,
    }


def test_query_competitor_summary_without_context_returns_error():
    result = _json_from_tool(query_competitor_summary)

    assert result["ok"] is False
    assert result["data"] is None
    assert result["errorType"] == "TOOL_CONTEXT_MISSING"
    assert "ToolContext" in result["errorMessage"]


def test_summarize_product_data_has_no_arguments_schema():
    assert list(signature(summarize_product_data.func).parameters) == []
    assert summarize_product_data.args_schema.model_json_schema()["properties"] == {}


def test_summarize_product_data_uses_payload_context():
    ctx = ToolContext(
        payload=_payload(),
        task_id=55,
        execution_id="exec-1",
        agent_code="DATA_ANALYSIS",
    )
    token = active_tool_context.set(ctx)
    try:
        result = _json_from_tool(summarize_product_data)
    finally:
        active_tool_context.reset(token)

    assert result["ok"] is True
    assert result["errorType"] is None
    assert result["data"]["productId"] == 101
    assert result["data"]["currentPrice"] == "29.90"
    assert result["data"]["costPrice"] == "16.80"
    assert result["data"]["stock"] == 250
    assert result["data"]["monthlySales"] == 22
    assert result["data"]["totalVisitors"] == 220


def test_summarize_product_data_does_not_return_price_recommendation():
    ctx = ToolContext(
        payload=_payload(),
        task_id=55,
        execution_id="exec-1",
        agent_code="DATA_ANALYSIS",
    )
    token = active_tool_context.set(ctx)
    try:
        dumped = json.dumps(_json_from_tool(summarize_product_data), ensure_ascii=False)
    finally:
        active_tool_context.reset(token)

    assert "suggestedPrice" not in dumped
    assert "finalPrice" not in dumped
    assert "expectedSales" not in dumped
    assert "expectedProfit" not in dumped


def test_tool_registry_returns_role_scoped_tools():
    assert [tool.name for tool in get_tools_for_agent("DATA_ANALYSIS")] == [
        "summarize_product_data",
        "estimate_sales_volume",
        "estimate_profit",
    ]
    assert [tool.name for tool in get_tools_for_agent("MARKET_INTEL")] == ["query_competitor_summary"]
    assert [tool.name for tool in get_tools_for_agent("RISK_CONTROL")] == ["evaluate_risk_rules"]
    assert [tool.name for tool in get_tools_for_agent("MANAGER_COORDINATOR")] == [
        "estimate_sales_volume",
        "estimate_profit",
        "evaluate_risk_rules",
    ]


def test_tool_registry_checks_authorization_by_agent_code():
    assert allowed_tool_names("DATA_ANALYSIS") == {
        "summarize_product_data",
        "estimate_sales_volume",
        "estimate_profit",
    }
    assert is_tool_allowed("DATA_ANALYSIS", "estimate_profit") is True
    assert is_tool_allowed("DATA_ANALYSIS", "query_competitor_summary") is False
    assert allowed_tool_names("MANAGER_COORDINATOR") == {
        "estimate_sales_volume",
        "estimate_profit",
        "evaluate_risk_rules",
    }
    assert is_tool_allowed("MANAGER_COORDINATOR", "evaluate_risk_rules") is True
    assert is_tool_allowed("MANAGER_COORDINATOR", "query_competitor_summary") is False
    assert is_tool_allowed("UNKNOWN_AGENT", "estimate_profit") is False


def test_evaluate_risk_rules_accepts_force_manual_review():
    result = json.loads(
        evaluate_risk_rules.func(
            current_price=100,
            cost_price=50,
            candidate_price=90,
            min_profit_rate=0.15,
            max_discount_rate=0.5,
            min_price=0,
            max_price=0,
            force_manual_review=True,
        )
    )

    assert result["is_pass"] is False
    assert result["need_manual_review"] is True


def test_tools_raise_when_worker_shutdown_requested():
    request_shutdown()
    try:
        try:
            summarize_product_data.func()
            raise AssertionError("expected TaskCancelledError")
        except TaskCancelledError:
            pass
    finally:
        clear_shutdown()
