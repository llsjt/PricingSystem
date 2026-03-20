"""淘宝抓取模块，优先尝试实时抓取，失败时返回明确风控状态。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from pricing_crew.config.runtime import settings


class TaobaoCrawlerBlockedError(RuntimeError):
    """淘宝页面触发风控或未能返回可用竞品数据。"""


@dataclass
class TaobaoProduct:
    product_id: str
    title: str
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
    location: str
    crawl_time: datetime


def _deep_find_product_lists(node: Any) -> Iterable[List[Dict[str, Any]]]:
    if isinstance(node, list):
        if node and all(isinstance(item, dict) for item in node):
            if any(
                any(key in item for key in ("title", "itemTitle", "name", "auctionTitle", "shopName"))
                for item in node
            ):
                yield node
        for item in node:
            yield from _deep_find_product_lists(item)
    elif isinstance(node, dict):
        for value in node.values():
            yield from _deep_find_product_lists(value)


def _strip_jsonp_wrapper(body: str) -> Dict[str, Any]:
    text = body.strip()
    match = re.match(r"^[A-Za-z0-9_]+\((.*)\)\s*;?$", text, re.S)
    if match:
        text = match.group(1)
    return json.loads(text)


def _parse_price(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"\d+(?:\.\d+)?", value.replace(",", ""))
        if match:
            return float(match.group(0))
    return None


def _parse_int(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        match = re.search(r"\d+", value.replace(",", ""))
        if match:
            return int(match.group(0))
    return 0


def _normalize_candidate(candidate: Dict[str, Any]) -> Optional[TaobaoProduct]:
    title = (
        candidate.get("title")
        or candidate.get("itemTitle")
        or candidate.get("auctionTitle")
        or candidate.get("name")
    )
    price = _parse_price(
        candidate.get("price")
        or candidate.get("priceShow")
        or candidate.get("discountPrice")
        or candidate.get("priceText")
    )
    if not title or price is None:
        return None

    url = (
        candidate.get("itemUrl")
        or candidate.get("auctionUrl")
        or candidate.get("detailUrl")
        or candidate.get("url")
        or ""
    )
    if url.startswith("//"):
        url = f"https:{url}"
    if url and "taobao.com" not in url and "tmall.com" not in url:
        url = ""

    item_id = str(
        candidate.get("itemId")
        or candidate.get("nid")
        or candidate.get("auctionId")
        or candidate.get("id")
        or title
    )
    shop_name = str(candidate.get("shopName") or candidate.get("sellerName") or "未知店铺")
    shop_type = "tmall" if "天猫" in shop_name.lower() or candidate.get("tmall") else "taobao"
    promo_tags = [
        str(tag)
        for tag in (
            candidate.get("promotionTags")
            or candidate.get("recommendTags")
            or candidate.get("tags")
            or []
        )
        if tag
    ]

    return TaobaoProduct(
        product_id=item_id,
        title=str(title).strip(),
        price=round(price, 2),
        original_price=_parse_price(candidate.get("originalPrice") or candidate.get("linePrice")),
        sales_volume=_parse_int(candidate.get("salesVolume") or candidate.get("soldText") or candidate.get("sellCount")),
        rating=max(0.0, min(5.0, _parse_price(candidate.get("rating") or candidate.get("shopDsr")) or 0.0)),
        review_count=_parse_int(candidate.get("reviewCount") or candidate.get("commentCount")),
        shop_name=shop_name,
        shop_type=shop_type,
        is_self_operated=bool(candidate.get("tmall") or candidate.get("isSelfSupport")),
        promotion_tags=promo_tags,
        product_url=url or f"https://s.taobao.com/search?q={quote(str(title))}",
        image_url=candidate.get("picUrl") or candidate.get("imageUrl"),
        location=str(candidate.get("location") or candidate.get("itemLoc") or "CN"),
        crawl_time=datetime.now(timezone.utc),
    )


class TaobaoWebCrawler:
    """基于 Playwright 的淘宝实时抓取器。"""

    def __init__(self) -> None:
        self.last_fetch_meta: Dict[str, Any] = {}

    def _extract_candidates_from_responses(self, responses: List[str]) -> List[TaobaoProduct]:
        products: List[TaobaoProduct] = []
        seen_ids: set[str] = set()
        for body in responses:
            try:
                data = _strip_jsonp_wrapper(body)
            except Exception:
                continue
            for candidate_list in _deep_find_product_lists(data):
                for candidate in candidate_list:
                    product = _normalize_candidate(candidate)
                    if product is None or product.product_id in seen_ids:
                        continue
                    seen_ids.add(product.product_id)
                    products.append(product)
        return products

    def search_products(self, keyword: str, limit: int = 10) -> List[TaobaoProduct]:
        search_url = f"https://s.taobao.com/search?q={quote(keyword)}"
        captured_bodies: List[str] = []
        taobao_results: List[TaobaoProduct] = []
        blocked_reason = ""

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=settings.taobao_browser_executable or None,
                headless=settings.taobao_browser_headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                viewport={"width": 1440, "height": 1200},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
                ),
                locale="zh-CN",
            )
            page = context.new_page()

            def on_response(response) -> None:
                if "h5api.m.taobao.com" not in response.url:
                    return
                if any(flag in response.url for flag in ("_____tmd_____", "punish", "captcha")):
                    return
                try:
                    body = response.text()
                except Exception:
                    return
                if body:
                    captured_bodies.append(body)

            page.on("response", on_response)
            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=settings.taobao_crawler_timeout_ms)
                page.wait_for_timeout(settings.taobao_crawler_wait_ms)
                taobao_results = self._extract_candidates_from_responses(captured_bodies)

                if not taobao_results:
                    body_text = page.locator("body").inner_text(timeout=3000)
                    if "加载中" in body_text or "请登录" in body_text:
                        blocked_reason = "淘宝搜索页返回骨架屏或登录风控，未获取到可用竞品。"
                    else:
                        blocked_reason = "淘宝搜索页未返回可解析的竞品数据。"

                self.last_fetch_meta = {
                    "source": "taobao_live",
                    "blocked": bool(blocked_reason),
                    "warnings": [blocked_reason] if blocked_reason else [],
                    "search_url": search_url,
                }
                if blocked_reason:
                    raise TaobaoCrawlerBlockedError(blocked_reason)
                return taobao_results[:limit]
            except PlaywrightTimeoutError as exc:
                blocked_reason = f"淘宝搜索页超时：{exc}"
                self.last_fetch_meta = {
                    "source": "taobao_live",
                    "blocked": True,
                    "warnings": [blocked_reason],
                    "search_url": search_url,
                }
                raise TaobaoCrawlerBlockedError(blocked_reason) from exc
            finally:
                context.close()
                browser.close()


taobao_crawler = TaobaoWebCrawler()
