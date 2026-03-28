from decimal import Decimal


class CompetitorParseTool:
    def summarize(self, items: list[dict]) -> dict:
        if not items:
            return {
                "sample_count": 0,
                "price_floor": Decimal("0.00"),
                "price_ceiling": Decimal("0.00"),
                "average_price": Decimal("0.00"),
                "promo_pressure": "LOW",
            }

        prices = [Decimal(str(row.get("price", 0))) for row in items]
        avg = sum(prices) / Decimal(len(prices))
        high_promo = sum(1 for row in items if row.get("promo_intensity") == "HIGH")
        promo_pressure = "HIGH" if high_promo >= len(items) // 2 else "MEDIUM"
        return {
            "sample_count": len(items),
            "price_floor": min(prices).quantize(Decimal("0.01")),
            "price_ceiling": max(prices).quantize(Decimal("0.01")),
            "average_price": avg.quantize(Decimal("0.01")),
            "promo_pressure": promo_pressure,
        }

