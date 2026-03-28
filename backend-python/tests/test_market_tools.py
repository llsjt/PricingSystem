from decimal import Decimal

from app.tools.competitor_crawler_tool import CompetitorCrawlerTool
from app.tools.competitor_parse_tool import CompetitorParseTool
from app.tools.competitor_search_tool import CompetitorSearchTool


def test_market_tools_simulation_pipeline() -> None:
    search_tool = CompetitorSearchTool()
    crawler_tool = CompetitorCrawlerTool()
    parse_tool = CompetitorParseTool()

    hits = search_tool.search("女装/裤子", Decimal("129.00"))
    assert len(hits) >= 5

    detail_rows = crawler_tool.fetch_details(hits)
    assert len(detail_rows) == len(hits)

    summary = parse_tool.summarize(detail_rows)
    assert summary["sample_count"] == len(hits)
    assert summary["price_floor"] <= summary["average_price"] <= summary["price_ceiling"]

