"""CrewAI 工具集合模块，负责组装可被智能体调用的工具对象。"""

import json
from decimal import Decimal
from typing import Any

from crewai.tools import tool

from app.tools.elasticity_profit_tool import ElasticityProfitTool
from app.tools.product_data_tool import ProductDataTool
from app.tools.risk_rule_tool import RiskRuleTool
from app.tools.tool_context import active_tool_context

_elasticity_tool = ElasticityProfitTool()
_product_data_tool = ProductDataTool()
_risk_rule_tool = RiskRuleTool()


def _default_serializer(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return str(obj)
    return str(obj)


def _tool_success(data: Any) -> str:
    return json.dumps(
        {
            "ok": True,
            "data": data,
            "errorType": None,
            "errorMessage": None,
        },
        ensure_ascii=False,
        default=_default_serializer,
    )


def _tool_error(error_type: str, error_message: str) -> str:
    return json.dumps(
        {
            "ok": False,
            "data": None,
            "errorType": error_type,
            "errorMessage": error_message,
        },
        ensure_ascii=False,
    )


def _product_snapshot_data(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "productId": summary.get("product_id"),
        "currentPrice": summary.get("current_price"),
        "costPrice": summary.get("cost_price"),
        "stock": summary.get("stock"),
        "monthlySales": summary.get("monthly_sales"),
        "monthlyTurnover": summary.get("monthly_turnover"),
        "averageConversionRate": summary.get("average_conversion_rate"),
        "totalVisitors": summary.get("total_visitors"),
        "trafficCtr": summary.get("traffic_ctr"),
    }


@tool("summarize_product_data")
def summarize_product_data() -> str:
    """返回当前商品经营快照，不生成建议价，不做销量或利润测算。"""
    ctx = active_tool_context.get()
    if ctx is None:
        return _tool_error("TOOL_CONTEXT_MISSING", "summarize_product_data requires active ToolContext")

    summary = _product_data_tool.summarize(
        product=ctx.payload.product,
        metrics=ctx.payload.metrics,
        traffic=ctx.payload.traffic,
    )
    return _tool_success(_product_snapshot_data(summary))


@tool("query_competitor_summary")
def query_competitor_summary() -> str:
    """返回当前商品的预计算竞品摘要，不实时查询外部数据源。"""
    ctx = active_tool_context.get()
    if ctx is None:
        return _tool_error("TOOL_CONTEXT_MISSING", "query_competitor_summary requires active ToolContext")
    if not ctx.precomputed_competitor_summary:
        return _tool_error(
            "COMPETITOR_SUMMARY_MISSING",
            "query_competitor_summary requires precomputed competitor summary",
        )

    return _tool_success({"summary": ctx.precomputed_competitor_summary})


@tool("estimate_sales_volume")
def estimate_sales_volume(
    baseline_sales: int,
    current_price: float,
    target_price: float,
    strategy_goal: str,
) -> str:
    """估算调价后的月销量。"""
    estimated = _elasticity_tool.estimate_sales(
        baseline_sales=int(baseline_sales),
        current_price=Decimal(str(current_price)),
        target_price=Decimal(str(target_price)),
        strategy_goal=str(strategy_goal),
    )
    return json.dumps({"estimated_sales": estimated}, ensure_ascii=False)


@tool("estimate_profit")
def estimate_profit(
    price: float,
    cost_price: float,
    expected_sales: int,
) -> str:
    """根据售价、成本价和预期销量估算月利润。"""
    profit = _elasticity_tool.estimate_profit(
        price=Decimal(str(price)),
        cost_price=Decimal(str(cost_price)),
        expected_sales=int(expected_sales),
    )
    return json.dumps({"estimated_profit": str(profit)}, ensure_ascii=False)


@tool("evaluate_risk_rules")
def evaluate_risk_rules(
    current_price: float,
    cost_price: float,
    candidate_price: float,
    min_profit_rate: float = 0.15,
    max_discount_rate: float = 0.5,
    min_price: float = 0.0,
    max_price: float = 0.0,
) -> str:
    """评估候选价格是否满足硬性风控规则。"""
    constraints: dict[str, Any] = {
        "min_profit_rate": min_profit_rate,
        "max_discount_rate": max_discount_rate,
    }
    if min_price > 0:
        constraints["min_price"] = min_price
    if max_price > 0:
        constraints["max_price"] = max_price
    result = _risk_rule_tool.evaluate(
        current_price=Decimal(str(current_price)),
        cost_price=Decimal(str(cost_price)),
        candidate_price=Decimal(str(candidate_price)),
        constraints=constraints,
    )
    return json.dumps(result, ensure_ascii=False, default=_default_serializer)
