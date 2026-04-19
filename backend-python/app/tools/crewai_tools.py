import json
from decimal import Decimal
from typing import Any

from crewai.tools import tool

from app.tools.elasticity_profit_tool import ElasticityProfitTool
from app.tools.risk_rule_tool import RiskRuleTool

_elasticity_tool = ElasticityProfitTool()
_risk_rule_tool = RiskRuleTool()


def _default_serializer(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return str(obj)
    return str(obj)


@tool("estimate_sales_volume")
def estimate_sales_volume(
    baseline_sales: int,
    current_price: float,
    target_price: float,
    strategy_goal: str,
) -> str:
    """Estimate monthly sales volume after a price change."""
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
    """Estimate monthly profit from price, cost, and expected sales."""
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
    """Evaluate hard pricing risk rules for a candidate price."""
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
