from decimal import Decimal

from app.schemas.agent import MarketAgentOutput, ProductContext
from app.services.competitor_service import CompetitorService
from app.utils.math_utils import money


class MarketIntelAgent:
    code = "MARKET_INTEL"
    name = "市场情报Agent"

    def __init__(self) -> None:
        # 通过独立 service 获取模拟竞品数据，避免在 prompt 中写死样本。
        self.competitor_service = CompetitorService()

    @staticmethod
    def _summarize_market(competitors: list[dict]) -> dict[str, Decimal | int]:
        prices = [Decimal(str(item.get("price", 0))) for item in competitors if item.get("price") is not None]
        if not prices:
            return {
                "sample_count": 0,
                "price_floor": Decimal("0.00"),
                "price_ceiling": Decimal("0.00"),
                "average_price": Decimal("0.00"),
            }

        avg = sum(prices) / Decimal(len(prices))
        return {
            "sample_count": len(prices),
            "price_floor": min(prices).quantize(Decimal("0.01")),
            "price_ceiling": max(prices).quantize(Decimal("0.01")),
            "average_price": avg.quantize(Decimal("0.01")),
        }

    def run(self, product: ProductContext, strategy_goal: str) -> MarketAgentOutput:
        competitors = self.competitor_service.get_competitors(
            product_id=product.product_id,
            product_title=product.product_name,
            category_name=product.category_name,
            current_price=product.current_price,
        )
        market = self._summarize_market(competitors)

        avg = money(market["average_price"])
        floor = money(market["price_floor"])
        ceiling = money(market["price_ceiling"])

        if strategy_goal.upper() == "CLEARANCE":
            suggested = money(max(floor, avg * Decimal("0.98")))
        elif strategy_goal.upper() == "MAX_PROFIT":
            suggested = money(min(ceiling, avg * Decimal("1.03")))
        else:
            suggested = avg

        return MarketAgentOutput(
            suggestedPrice=suggested,
            marketFloor=floor,
            marketCeiling=ceiling,
            confidence=0.75,
            summary=(
                f"基于 {market['sample_count']} 条模拟竞品信息，判断主价格带为 {floor}~{ceiling}，"
                f"建议价格 {suggested}。"
            ),
            simulatedSamples=int(market["sample_count"]),
        )
