from decimal import Decimal

from app.utils.math_utils import money


class RiskRuleTool:
    def evaluate(
        self,
        current_price: Decimal,
        cost_price: Decimal,
        candidate_price: Decimal,
        constraints: dict,
    ) -> dict:
        min_profit_rate = Decimal(str(constraints.get("min_profit_rate", "0.15")))
        min_price = constraints.get("min_price")
        max_price = constraints.get("max_price")
        max_discount_rate = constraints.get("max_discount_rate")
        force_manual_review = bool(constraints.get("force_manual_review", False))

        floor_by_profit = Decimal(str(cost_price)) / (Decimal("1.0") - min_profit_rate)
        safe_floor = money(max(Decimal(str(cost_price)) * Decimal("1.05"), floor_by_profit))

        final_floor = safe_floor
        if min_price is not None:
            final_floor = max(final_floor, money(min_price))

        suggested = money(max(Decimal(str(candidate_price)), final_floor))
        if max_discount_rate is not None:
            max_drop = money(Decimal(str(current_price)) * (Decimal("1.0") - Decimal(str(max_discount_rate))))
            suggested = max(suggested, max_drop)

        if max_price is not None:
            suggested = money(min(suggested, money(max_price)))

        margin = Decimal("0.0")
        if suggested > 0:
            margin = (suggested - Decimal(str(cost_price))) / suggested

        is_pass = suggested >= final_floor and margin >= min_profit_rate and not force_manual_review
        risk_level = "LOW" if is_pass else "HIGH"
        return {
            "is_pass": is_pass,
            "safe_floor_price": money(final_floor),
            "suggested_price": money(suggested),
            "risk_level": risk_level,
            "need_manual_review": (not is_pass) or force_manual_review,
            "margin": margin.quantize(Decimal("0.0000")),
        }

