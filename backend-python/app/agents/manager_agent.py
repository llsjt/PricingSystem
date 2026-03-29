from decimal import Decimal
from typing import Any

from app.schemas.agent import DataAgentOutput, ManagerAgentOutput, MarketAgentOutput, RiskAgentOutput
from app.tools.elasticity_profit_tool import ElasticityProfitTool
from app.utils.math_utils import clamp_decimal, money


class ManagerAgent:
    code = "MANAGER_COORDINATOR"
    name = "经理协调Agent"

    def __init__(self) -> None:
        self.elasticity_tool = ElasticityProfitTool()

    def run(
        self,
        strategy_goal: str,
        current_price: Decimal,
        cost_price: Decimal,
        baseline_profit: Decimal,
        baseline_sales: int,
        data_result: DataAgentOutput,
        market_result: MarketAgentOutput,
        risk_result: RiskAgentOutput,
        crewai_hint: dict[str, Any] | None = None,
    ) -> ManagerAgentOutput:
        prices = [
            money(data_result.suggested_price),
            money(market_result.suggested_price),
            money(risk_result.suggested_price),
        ]
        suggested_min = money(min(prices))
        suggested_max = money(max(prices))

        strategy = (strategy_goal or "").upper()
        if strategy == "CLEARANCE":
            candidate = money(min(data_result.suggested_price, market_result.suggested_price))
        elif strategy == "MARKET_SHARE":
            candidate = money((data_result.suggested_price + market_result.suggested_price) / Decimal("2"))
        else:
            candidate = money(max(data_result.suggested_price, market_result.suggested_price))

        hint_price: Decimal | None = None
        if isinstance(crewai_hint, dict):
            raw_hint_price = crewai_hint.get("recommendedPrice")
            try:
                if raw_hint_price is not None:
                    parsed = money(raw_hint_price)
                    if parsed > 0:
                        hint_price = parsed
            except Exception:
                hint_price = None

        if hint_price is not None:
            candidate = money(candidate * Decimal("0.70") + hint_price * Decimal("0.30"))

        final_price = clamp_decimal(candidate, money(risk_result.safe_floor_price), money(market_result.market_ceiling))
        final_price = money(max(final_price, money(risk_result.suggested_price)))

        expected_sales = self.elasticity_tool.estimate_sales(
            baseline_sales=baseline_sales,
            current_price=money(current_price),
            target_price=final_price,
            strategy_goal=strategy,
        )
        expected_profit = self.elasticity_tool.estimate_profit(final_price, money(cost_price), expected_sales)
        profit_growth = money(expected_profit - money(baseline_profit))

        is_pass = bool(risk_result.is_pass) and final_price >= money(risk_result.safe_floor_price)
        if not is_pass:
            execute_strategy = "人工审核"
        elif profit_growth > 0:
            execute_strategy = "直接执行"
        else:
            execute_strategy = "灰度发布"

        summary = (
            f"综合数据、市场、风控意见，最终建议价 {final_price}，预计销量 {expected_sales}，"
            f"预计利润 {expected_profit}，利润变化 {profit_growth}，执行策略 {execute_strategy}。"
        )
        if hint_price is not None:
            summary += f"协作引擎提示价 {hint_price} 已作为辅助信号。"

        return ManagerAgentOutput(
            finalPrice=final_price,
            expectedSales=expected_sales,
            expectedProfit=expected_profit,
            profitGrowth=profit_growth,
            executeStrategy=execute_strategy,
            isPass=is_pass,
            resultSummary=summary,
            suggestedMinPrice=suggested_min,
            suggestedMaxPrice=suggested_max,
        )
