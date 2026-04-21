"""基于天猫真实 CSV 的竞品 Provider。

匹配链：
1. 二级类目精确匹配（销量降序 top-N）
2. 一级类目精确匹配
3. 商品标题关键词模糊匹配
4. SQLite 不可用或全无命中时返回空结果，不生成模拟竞品。

除了基础 competitors 列表外，本 provider 还会在结果里附带新维度统计：
brandBreakdown / shopTypeBreakdown / salesWeightedAverage / promotionDensity，
供 prompt summary 与前端 evidence 使用。
"""
# 天猫 CSV 竞品提供者，用于从本地竞品数据源生成市场情报输入。

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from statistics import median
from typing import Any

from app.repos.competitor_csv_repo import CompetitorCsvRepo


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _format_sales_hint(value: Any) -> str:
    parsed = _safe_int(value)
    if parsed is None or parsed <= 0:
        return "销量数据暂缺"
    if parsed >= 10000:
        return f"年销量约{parsed / 10000:.1f}万件"
    return f"年销量约{parsed}件"


def _row_to_competitor(row: dict[str, Any]) -> dict[str, Any]:
    final_price = _safe_float(row.get("final_price"))
    discount_price = _safe_float(row.get("discount_price"))
    original_price = _safe_float(row.get("original_price"))
    price = final_price or discount_price or original_price
    if price is None:
        return {}
    name = (
        (row.get("shop_name") or row.get("brand") or row.get("short_title") or "未知竞品")
        .strip()
    )
    return {
        "competitorName": name or "未知竞品",
        "price": round(price, 2),
        "originalPrice": round(original_price, 2) if original_price else None,
        "salesVolumeHint": _format_sales_hint(row.get("yearly_sales")),
        "promotionTag": (row.get("promotion_tag") or "").strip() or "常规促销",
        "shopType": (row.get("shop_type") or "").strip() or None,
        "sourcePlatform": "天猫",
        # 透传到 provider 内部的扩展统计（不会被 schema 校验丢失，因为 schema 只读取已知字段）
        "_brand": (row.get("brand") or "").strip() or None,
        "_yearlySales": _safe_int(row.get("yearly_sales")) or 0,
    }


def _build_brand_breakdown(competitors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for item in competitors:
        brand = item.get("_brand")
        price = _safe_float(item.get("price"))
        if not brand or price is None:
            continue
        grouped[brand].append(price)
    bands: list[dict[str, Any]] = []
    for brand, prices in grouped.items():
        if not prices:
            continue
        bands.append(
            {
                "brand": brand,
                "sampleCount": len(prices),
                "averagePrice": round(sum(prices) / len(prices), 2),
                "medianPrice": round(float(median(prices)), 2),
                "minPrice": round(min(prices), 2),
                "maxPrice": round(max(prices), 2),
            }
        )
    bands.sort(key=lambda b: (-b["sampleCount"], b["averagePrice"]))
    return bands[:5]


def _build_shop_type_breakdown(competitors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    total = 0
    for item in competitors:
        shop_type = (item.get("shopType") or "").strip()
        price = _safe_float(item.get("price"))
        if price is None:
            continue
        total += 1
        grouped[shop_type or "其他"].append(price)
    if total == 0:
        return []
    breakdown: list[dict[str, Any]] = []
    for shop_type, prices in grouped.items():
        breakdown.append(
            {
                "shopType": shop_type,
                "sampleCount": len(prices),
                "share": round(len(prices) / total, 3),
                "averagePrice": round(sum(prices) / len(prices), 2),
            }
        )
    breakdown.sort(key=lambda b: -b["sampleCount"])
    return breakdown


def _build_sales_weighted(competitors: list[dict[str, Any]]) -> dict[str, float | None]:
    weighted_sum = 0.0
    weight_total = 0
    sortable: list[tuple[float, int]] = []
    for item in competitors:
        price = _safe_float(item.get("price"))
        sales = int(item.get("_yearlySales") or 0)
        if price is None or sales <= 0:
            continue
        weighted_sum += price * sales
        weight_total += sales
        sortable.append((price, sales))
    if weight_total == 0:
        return {"salesWeightedAverage": None, "salesWeightedMedian": None}
    weighted_average = round(weighted_sum / weight_total, 2)
    sortable.sort(key=lambda t: t[0])
    cumulative = 0
    half = weight_total / 2
    weighted_median: float | None = None
    for price, sales in sortable:
        cumulative += sales
        if cumulative >= half:
            weighted_median = round(price, 2)
            break
    return {
        "salesWeightedAverage": weighted_average,
        "salesWeightedMedian": weighted_median,
    }


def _build_promotion_density(competitors: list[dict[str, Any]]) -> dict[str, float | int | None]:
    if not competitors:
        return {"promotionRate": None, "averageDiscount": None, "promotedSampleCount": 0}
    promoted = 0
    discount_sum = 0.0
    discount_count = 0
    for item in competitors:
        tag = (item.get("promotionTag") or "").strip()
        if tag and tag not in {"常规促销", "无", "-"}:
            promoted += 1
        price = _safe_float(item.get("price"))
        original = _safe_float(item.get("originalPrice"))
        if price and original and original > 0:
            ratio = price / original
            if 0 < ratio <= 1.0:
                discount_sum += ratio
                discount_count += 1
    promotion_rate = round(promoted / len(competitors), 3)
    average_discount = round(discount_sum / discount_count, 3) if discount_count else None
    return {
        "promotionRate": promotion_rate,
        "averageDiscount": average_discount,
        "promotedSampleCount": promoted,
    }


def _strip_internal_fields(competitors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for item in competitors:
        cleaned.append({k: v for k, v in item.items() if not k.startswith("_")})
    return cleaned


class TmallCsvCompetitorProvider:
    """从 SQLite 索引按类目/标题匹配真实天猫竞品。"""

    source = "TMALL_CSV"

    def __init__(
        self,
        repo: CompetitorCsvRepo | None = None,
        *,
        sample_size: int = 8,
    ) -> None:
        self.repo = repo or CompetitorCsvRepo()
        self.sample_size = max(int(sample_size), 1)

    # ── 主入口 ───────────────────────────────────────────────
    def fetch(
        self,
        *,
        product_id: int,
        product_title: str | None,
        category_name: str | None,
        current_price: Decimal,
    ) -> dict[str, Any]:
        if not self.repo.available:
            return self._empty_result("UNCONFIGURED", message="competitor index missing")

        rows = self._lookup(product_title, category_name)
        if not rows:
            return self._empty_result("EMPTY", message="no category/title match")

        competitors = [c for c in (_row_to_competitor(r) for r in rows) if c]
        if not competitors:
            return self._empty_result("EMPTY", message="rows lacked usable price")

        brand_breakdown = _build_brand_breakdown(competitors)
        shop_type_breakdown = _build_shop_type_breakdown(competitors)
        sales_weighted = _build_sales_weighted(competitors)
        promotion_density = _build_promotion_density(competitors)
        return {
            "sourceStatus": "OK",
            "source": self.source,
            "message": "tmall csv match",
            "rawItemCount": len(rows),
            "competitors": _strip_internal_fields(competitors),
            "brandBreakdown": brand_breakdown,
            "shopTypeBreakdown": shop_type_breakdown,
            "salesWeightedAverage": sales_weighted["salesWeightedAverage"],
            "salesWeightedMedian": sales_weighted["salesWeightedMedian"],
            "promotionDensity": promotion_density,
        }

    # ── 匹配链 ───────────────────────────────────────────────
    def _lookup(self, product_title: str | None, category_name: str | None) -> list[dict[str, Any]]:
        category = (category_name or "").strip()
        title = (product_title or "").strip()
        limit = self.sample_size

        if category:
            rows = self.repo.query_by_secondary_category(category, limit)
            if rows:
                return rows
            rows = self.repo.query_by_primary_category(category, limit)
            if rows:
                return rows
        for keyword in self._extract_keywords(title):
            rows = self.repo.query_by_keyword(keyword, limit)
            if rows:
                return rows
        return []

    @staticmethod
    def _extract_keywords(title: str) -> list[str]:
        text = title.strip()
        if not text:
            return []
        # 简单启发式：取前 4 个汉字 + 前 3 个汉字 + 第一段空白前的子串
        candidates: list[str] = []
        cleaned = text.replace("\u3000", " ")
        head = cleaned.split(" ", 1)[0]
        if head and head != cleaned:
            candidates.append(head)
        if len(cleaned) >= 4:
            candidates.append(cleaned[:4])
        if len(cleaned) >= 3:
            candidates.append(cleaned[:3])
        seen: set[str] = set()
        result: list[str] = []
        for value in candidates:
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result

# ── 空结果兜底 ─────────────────────────────────────────
    def _empty_result(self, source_status: str, *, message: str) -> dict[str, Any]:
        return {
            "sourceStatus": source_status,
            "source": self.source,
            "message": message,
            "rawItemCount": 0,
            "competitors": [],
        }
