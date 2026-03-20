"""淘宝抓取子进程入口，用于隔离 Playwright 与服务事件循环。"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict

from pricing_crew.crawlers.taobao_web_crawler import TaobaoCrawlerBlockedError, taobao_crawler


def build_payload(keyword: str, limit: int) -> Dict[str, Any]:
    try:
        competitors = taobao_crawler.search_products(keyword=keyword, limit=limit)
        meta = dict(taobao_crawler.last_fetch_meta)
        return {
            "success": bool(competitors),
            "blocked": bool(meta.get("blocked")),
            "source": meta.get("source", "taobao_live"),
            "keyword": keyword,
            "warnings": list(meta.get("warnings", [])),
            "competitors": [
                {
                    "competitor_id": item.product_id,
                    "product_name": item.title,
                    "current_price": item.price,
                    "original_price": item.original_price,
                    "sales_volume": item.sales_volume,
                    "rating": item.rating,
                    "review_count": item.review_count,
                    "shop_name": item.shop_name,
                    "shop_type": item.shop_type,
                    "is_self_operated": item.is_self_operated,
                    "promotion_tags": item.promotion_tags,
                    "product_url": item.product_url,
                    "image_url": item.image_url,
                    "location": item.location,
                    "crawl_time": item.crawl_time.isoformat(),
                }
                for item in competitors
            ],
        }
    except TaobaoCrawlerBlockedError as exc:
        return {
            "success": False,
            "blocked": True,
            "source": "taobao_live",
            "keyword": keyword,
            "warnings": [str(exc)],
            "competitors": [],
        }
    except Exception as exc:
        return {
            "success": False,
            "blocked": False,
            "source": "taobao_live",
            "keyword": keyword,
            "warnings": [f"淘宝抓取异常：{exc}"],
            "competitors": [],
        }


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    keyword = argv[1] if len(argv) > 1 else ""
    limit = int(argv[2]) if len(argv) > 2 else 8
    print(json.dumps(build_payload(keyword=keyword, limit=limit), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
