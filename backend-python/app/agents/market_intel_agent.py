from decimal import Decimal

from app.schemas.agent import MarketAgentOutput, ProductContext
from app.tools.competitor_crawler_tool import CompetitorCrawlerTool
from app.tools.competitor_parse_tool import CompetitorParseTool
from app.tools.competitor_search_tool import CompetitorSearchTool
from app.utils.math_utils import money


class MarketIntelAgent:
    code = "MARKET"
    name = "市场情报Agent"

    def __init__(self) -> None:
        self.search_tool = CompetitorSearchTool()
        self.crawler_tool = CompetitorCrawlerTool()
        self.parse_tool = CompetitorParseTool()

    def run(self, product: ProductContext, strategy_goal: str) -> MarketAgentOutput:
        # 按用户要求：当前阶段不做真实爬虫，统一使用模拟竞品样本
        search_hits = self.search_tool.search(product.category_name, product.current_price)
        detail_rows = self.crawler_tool.fetch_details(search_hits)
        market = self.parse_tool.summarize(detail_rows)

        avg = money(market["average_price"])
        if strategy_goal.upper() == "CLEARANCE":
            suggested = money(max(market["price_floor"], avg * Decimal("0.98")))
        elif strategy_goal.upper() == "MAX_PROFIT":
            suggested = money(min(market["price_ceiling"], avg * Decimal("1.03")))
        else:
            suggested = avg

        return MarketAgentOutput(
            suggestedPrice=suggested,
            marketFloor=money(market["price_floor"]),
            marketCeiling=money(market["price_ceiling"]),
            confidence=0.72,
            summary=(
                f"基于 {market['sample_count']} 条模拟竞品样本，市场价带 "
                f"{money(market['price_floor'])}~{money(market['price_ceiling'])}，建议价 {suggested}"
            ),
            simulatedSamples=int(market["sample_count"]),
        )

