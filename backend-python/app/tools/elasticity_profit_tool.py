from decimal import Decimal

from app.utils.math_utils import money


class ElasticityProfitTool:
    def estimate_sales(
        self,
        baseline_sales: int,
        current_price: Decimal,
        target_price: Decimal,
        strategy_goal: str,
    ) -> int:
        baseline = max(int(baseline_sales or 0), 30)
        current = Decimal(str(current_price or 0))
        target = Decimal(str(target_price or 0))
        if current <= 0:
            return baseline

        ratio = (target - current) / current
        strategy = (strategy_goal or "").upper()
        if strategy == "CLEARANCE":
            sensitivity = Decimal("1.80")
        elif strategy == "MARKET_SHARE":
            sensitivity = Decimal("1.35")
        else:
            sensitivity = Decimal("0.90")
        factor = Decimal("1.00") - ratio * sensitivity
        factor = max(factor, Decimal("0.35"))
        return int((Decimal(baseline) * factor).quantize(Decimal("1")))

    def estimate_profit(self, price: Decimal, cost_price: Decimal, expected_sales: int) -> Decimal:
        unit_profit = Decimal(str(price or 0)) - Decimal(str(cost_price or 0))
        return money(unit_profit * Decimal(max(int(expected_sales or 0), 0)))

