from decimal import Decimal


class CompetitorSearchTool:
    """Simulated market sample finder. No real crawler is used."""

    def search(self, category_name: str | None, current_price: Decimal) -> list[dict]:
        category = category_name or "通用品类"
        base = Decimal(str(current_price or 0))
        if base <= 0:
            base = Decimal("99.00")
        return [
            {"platform": "淘宝", "category": category, "price": (base * Decimal("0.93")).quantize(Decimal("0.01"))},
            {"platform": "天猫", "category": category, "price": (base * Decimal("1.02")).quantize(Decimal("0.01"))},
            {"platform": "京东", "category": category, "price": (base * Decimal("0.98")).quantize(Decimal("0.01"))},
            {"platform": "拼多多", "category": category, "price": (base * Decimal("0.89")).quantize(Decimal("0.01"))},
            {"platform": "抖音", "category": category, "price": (base * Decimal("0.95")).quantize(Decimal("0.01"))},
        ]

