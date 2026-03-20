"""竞品抓取聚合模块，将淘宝抓取结果转为统一竞品结构。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from pricing_crew.crawlers.taobao_web_crawler import TaobaoCrawlerBlockedError, taobao_crawler


@dataclass
class CompetitorProduct:
    product_name: str
    price: float
    original_price: Optional[float]
    sales_volume: int
    rating: float
    review_count: int
    shop_name: str
    shop_type: str
    is_self_operated: bool
    promotion_tags: List[str]
    product_url: str
    image_url: Optional[str]
    crawl_time: datetime


class CompetitorCrawler:
    def __init__(self) -> None:
        self.last_fetch_meta: Dict[str, Any] = {}

    def search_competitors(
        self,
        keyword: str,
        category: str,
        platforms: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[CompetitorProduct]:
        _ = category
        _ = platforms
        try:
            items = taobao_crawler.search_products(keyword=keyword, limit=limit)
            self.last_fetch_meta = dict(taobao_crawler.last_fetch_meta)
            return [
                CompetitorProduct(
                    product_name=item.title,
                    price=item.price,
                    original_price=item.original_price,
                    sales_volume=item.sales_volume,
                    rating=item.rating,
                    review_count=item.review_count,
                    shop_name=item.shop_name,
                    shop_type=item.shop_type,
                    is_self_operated=item.is_self_operated,
                    promotion_tags=item.promotion_tags,
                    product_url=item.product_url,
                    image_url=item.image_url,
                    crawl_time=item.crawl_time,
                )
                for item in items
            ]
        except TaobaoCrawlerBlockedError as exc:
            self.last_fetch_meta = {
                "source": "taobao_live",
                "blocked": True,
                "warnings": [str(exc)],
            }
            return []


competitor_crawler = CompetitorCrawler()
