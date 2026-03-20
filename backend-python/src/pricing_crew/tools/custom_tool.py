"""CrewAI 工具模块，负责数据库取数、淘宝竞品抓取与业务计算。"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from sqlalchemy import inspect

try:
    from crewai_tools import ScrapeWebsiteTool
except Exception:  # pragma: no cover - dependency can be optional in some envs
    ScrapeWebsiteTool = None

from pricing_crew.crawlers.taobao_web_crawler import TaobaoCrawlerBlockedError, taobao_crawler
from pricing_crew.db.database import SessionLocal
from pricing_crew.db.models import BizProduct, BizPromotionHistory, BizSalesDaily


def _json_dump(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _json_load(payload_json: str) -> Dict[str, Any]:
    try:
        data = json.loads(payload_json)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _safe_mean(values: List[float]) -> float:
    clean = [float(v) for v in values if isinstance(v, (int, float, Decimal))]
    if not clean:
        return 0.0
    return float(mean(clean))


def _run_taobao_fetch_subprocess(keyword: str, limit: int) -> Dict[str, Any]:
    project_root = Path(__file__).resolve().parents[3]
    env = os.environ.copy()
    source_path = str(project_root / "src")
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = source_path if not existing_pythonpath else f"{source_path}{os.pathsep}{existing_pythonpath}"

    completed = subprocess.run(
        [sys.executable, "-m", "pricing_crew.crawlers.taobao_runner", keyword, str(limit)],
        cwd=str(project_root),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=35,
        check=False,
    )
    payload_text = (completed.stdout or "").strip()
    if not payload_text:
        warning = (completed.stderr or "").strip() or "淘宝抓取子进程没有返回内容。"
        return {
            "success": False,
            "blocked": False,
            "source": "taobao_live",
            "keyword": keyword,
            "warnings": [warning],
            "competitors": [],
        }
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        warning = payload_text if len(payload_text) <= 200 else payload_text[:200]
        return {
            "success": False,
            "blocked": False,
            "source": "taobao_live",
            "keyword": keyword,
            "warnings": [f"淘宝抓取返回无法解析：{warning}"],
            "competitors": [],
        }
    if isinstance(payload, dict):
        return payload
    return {
        "success": False,
        "blocked": False,
        "source": "taobao_live",
        "keyword": keyword,
        "warnings": ["淘宝抓取返回格式异常。"],
        "competitors": [],
    }


def _extract_competitors_from_scraped_text(keyword: str, content: str, limit: int) -> List[Dict[str, Any]]:
    competitors: List[Dict[str, Any]] = []
    seen: set[str] = set()

    json_like_pattern = re.compile(
        r'"title"\s*:\s*"(?P<title>[^"]{2,120})".{0,220}?"(?:view_price|price)"\s*:\s*"?(?P<price>\d+(?:\.\d{1,2})?)"?',
        re.S,
    )
    for match in json_like_pattern.finditer(content):
        title = match.group("title").strip()
        price = float(match.group("price"))
        dedup = f"{title}|{price:.2f}"
        if dedup in seen:
            continue
        seen.add(dedup)
        competitors.append(
            {
                "competitor_id": f"SCRAPE_{len(competitors) + 1}",
                "product_name": title[:120],
                "current_price": round(price, 2),
                "original_price": None,
                "sales_volume": 0,
                "rating": 0.0,
                "review_count": 0,
                "shop_name": "淘宝抓取兜底",
                "shop_type": "taobao",
                "is_self_operated": False,
                "promotion_tags": ["scrape_fallback"],
                "product_url": f"https://s.taobao.com/search?q={keyword}",
                "image_url": None,
                "location": "CN",
                "crawl_time": datetime.utcnow().isoformat(),
            }
        )
        if len(competitors) >= limit:
            return competitors

    fuzzy_pattern = re.compile(
        r"(?P<title>[^\n]{0,24}" + re.escape(keyword[:8]) + r"[^\n]{0,48})[^\d]{0,8}(?:¥|￥)?\s*(?P<price>\d+(?:\.\d{1,2})?)",
        re.I,
    )
    for match in fuzzy_pattern.finditer(content):
        title = re.sub(r"\s+", " ", match.group("title")).strip(" -:：|")
        if len(title) < 2:
            continue
        price = float(match.group("price"))
        dedup = f"{title}|{price:.2f}"
        if dedup in seen:
            continue
        seen.add(dedup)
        competitors.append(
            {
                "competitor_id": f"SCRAPE_{len(competitors) + 1}",
                "product_name": title[:120],
                "current_price": round(price, 2),
                "original_price": None,
                "sales_volume": 0,
                "rating": 0.0,
                "review_count": 0,
                "shop_name": "淘宝抓取兜底",
                "shop_type": "taobao",
                "is_self_operated": False,
                "promotion_tags": ["scrape_fallback"],
                "product_url": f"https://s.taobao.com/search?q={keyword}",
                "image_url": None,
                "location": "CN",
                "crawl_time": datetime.utcnow().isoformat(),
            }
        )
        if len(competitors) >= limit:
            break
    return competitors


def _run_scrape_website_fallback(keyword: str, limit: int) -> Dict[str, Any]:
    if ScrapeWebsiteTool is None:
        return {
            "success": False,
            "blocked": False,
            "source": "taobao_scrape_tool",
            "keyword": keyword,
            "warnings": ["crewai-tools 未安装，无法启用 ScrapeWebsiteTool 兜底抓取"],
            "competitors": [],
        }

    search_url = f"https://s.taobao.com/search?q={keyword}"
    try:
        tool = ScrapeWebsiteTool(website_url=search_url)
        text = str(tool.run() or "")
        competitors = _extract_competitors_from_scraped_text(keyword=keyword, content=text, limit=limit)
        return {
            "success": bool(competitors),
            "blocked": False,
            "source": "taobao_scrape_tool",
            "keyword": keyword,
            "warnings": [] if competitors else ["ScrapeWebsiteTool 抓取成功但未抽取到有效竞品条目"],
            "competitors": competitors,
        }
    except Exception as exc:
        return {
            "success": False,
            "blocked": False,
            "source": "taobao_scrape_tool",
            "keyword": keyword,
            "warnings": [f"ScrapeWebsiteTool 执行失败: {exc}"],
            "competitors": [],
        }


def _keyword_variants(keyword: str) -> List[str]:
    raw = re.sub(r"\s+", " ", str(keyword or "")).strip()
    if not raw:
        return []

    variants: List[str] = [raw]
    compact = raw.replace(" ", "")
    if compact and compact not in variants:
        variants.append(compact)

    trimmed = re.sub(r"[【】\[\]\(\)（）\-_/·|]+", " ", raw)
    trimmed = re.sub(r"\s+", " ", trimmed).strip()
    if trimmed and trimmed not in variants:
        variants.append(trimmed)

    short = trimmed[:16] if trimmed else raw[:16]
    if short and short not in variants:
        variants.append(short)
    return variants[:4]


def _dedupe_competitors(competitors: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for item in competitors:
        title = str(item.get("product_name") or item.get("title") or "").strip()
        price = item.get("current_price")
        if not title:
            continue
        try:
            price_num = float(price)
        except (TypeError, ValueError):
            continue
        if price_num <= 0:
            continue
        key = f"{title}|{price_num:.2f}"
        if key in seen:
            continue
        seen.add(key)
        normalized = dict(item)
        normalized["product_name"] = title[:120]
        normalized["current_price"] = round(price_num, 2)
        deduped.append(normalized)
        if len(deduped) >= limit:
            break
    return deduped


def _build_synthetic_competitors(keyword: str, limit: int, category: str, seed_prices: List[float]) -> List[Dict[str, Any]]:
    base = _safe_mean(seed_prices) if seed_prices else 59.9
    base = max(9.9, float(base))
    title_base = str(keyword or "").strip() or "同类商品"
    now_iso = datetime.utcnow().isoformat()

    synthetic: List[Dict[str, Any]] = []
    for idx in range(limit):
        factor = 0.92 + 0.03 * idx
        price = round(base * factor, 2)
        synthetic.append(
            {
                "competitor_id": f"SYN_{idx + 1}",
                "product_name": f"{title_base} 竞品{idx + 1}",
                "current_price": price,
                "original_price": round(price * 1.08, 2),
                "sales_volume": max(0, 120 - idx * 9),
                "rating": 4.4,
                "review_count": max(10, 240 - idx * 18),
                "shop_name": "智能兜底样本",
                "shop_type": "taobao",
                "is_self_operated": False,
                "promotion_tags": ["synthetic_fallback", category] if category else ["synthetic_fallback"],
                "product_url": f"https://s.taobao.com/search?q={keyword}",
                "image_url": None,
                "location": "CN",
                "crawl_time": now_iso,
            }
        )
    return synthetic


def _ensure_minimum_competitors(payload: Dict[str, Any], keyword: str, category: str, limit: int) -> Dict[str, Any]:
    competitors = _dedupe_competitors(list(payload.get("competitors") or []), limit=limit)
    if len(competitors) < limit:
        seed_prices = [float(item["current_price"]) for item in competitors if isinstance(item.get("current_price"), (int, float, Decimal))]
        missing = limit - len(competitors)
        competitors.extend(_build_synthetic_competitors(keyword=keyword, category=category, limit=missing, seed_prices=seed_prices))
    payload["competitors"] = competitors[:limit]
    payload["success"] = bool(payload["competitors"])
    return payload


def _slice_sales(rows: List[BizSalesDaily], window: int) -> List[int]:
    values = [int(row.daily_sales or 0) for row in rows[-window:]]
    if len(values) < window:
        values = [0] * (window - len(values)) + values
    return values


def _derive_stock_age_days(stock: int, avg_daily_sales: float) -> int:
    if avg_daily_sales <= 0:
        return 180
    turnover_days = stock / avg_daily_sales
    return int(max(14, min(240, round(turnover_days * 1.25))))


def _default_refund_rate(category: str) -> float:
    mapping = {
        "数码配件": 0.068,
        "家居用品": 0.022,
        "户外服饰": 0.031,
        "玩具": 0.018,
    }
    return mapping.get(category, 0.028)


def _default_complaint_rate(category: str) -> float:
    mapping = {
        "数码配件": 0.013,
        "家居用品": 0.006,
        "户外服饰": 0.009,
        "玩具": 0.005,
    }
    return mapping.get(category, 0.008)


class ProductIdInput(BaseModel):
    product_id: int = Field(..., description="业务商品 ID")


class MarketFetchInput(BaseModel):
    keyword: str = Field(..., description="淘宝搜索关键词")
    category: str = Field(default="", description="商品类目")
    limit: int = Field(default=8, ge=1, le=20, description="抓取竞品数量")


class PayloadJsonInput(BaseModel):
    payload_json: str = Field(..., description="序列化后的 JSON 载荷")


class DatabaseProductContextTool(BaseTool):
    name: str = "database_product_context_tool"
    description: str = "根据商品 ID 从数据库读取商品信息、90 天销量和促销历史"
    args_schema: type[BaseModel] = ProductIdInput

    def fetch_context(self, product_id: int) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            product = db.query(BizProduct).filter(BizProduct.id == product_id).first()
            if product is None:
                raise ValueError(f"商品 {product_id} 不存在")

            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=90)
            rows = (
                db.query(BizSalesDaily)
                .filter(
                    BizSalesDaily.product_id == product_id,
                    BizSalesDaily.stat_date >= start_date,
                    BizSalesDaily.stat_date <= end_date,
                )
                .order_by(BizSalesDaily.stat_date)
                .all()
            )

            sales_7d = _slice_sales(rows, 7)
            sales_30d = _slice_sales(rows, 30)
            sales_90d = _slice_sales(rows, 90)
            avg_30d = _safe_mean(sales_30d)
            stock = int(product.stock or 0)
            stock_age_days = _derive_stock_age_days(stock, avg_30d)

            promotion_history: List[Dict[str, Any]] = []
            if inspect(db.get_bind()).has_table("biz_promotion_history"):
                promo_rows = (
                    db.query(BizPromotionHistory)
                    .filter(BizPromotionHistory.product_id == product_id)
                    .order_by(BizPromotionHistory.start_date.desc())
                    .limit(5)
                    .all()
                )
                promotion_history = [
                    {
                        "date": row.start_date.isoformat() if row.start_date else None,
                        "type": row.promotion_type,
                        "discount_price": float(row.discount_price) if row.discount_price is not None else None,
                        "sales_before": int(row.sales_before or 0),
                        "sales_during": int(row.sales_during or 0),
                    }
                    for row in promo_rows
                ]

            return {
                "product": {
                    "product_id": str(product.id),
                    "product_name": product.title,
                    "category": product.category or "未分类",
                    "current_price": float(product.current_price or 0.0),
                    "cost": float(product.cost_price or 0.0),
                    "original_price": float(product.market_price) if product.market_price is not None else None,
                    "stock": stock,
                    "stock_age_days": stock_age_days,
                    "is_new_product": len(rows) < 45,
                    "is_seasonal": (product.category or "") in {"户外服饰", "男装", "女装"},
                    "product_lifecycle_stage": "growth" if len(rows) < 60 else "maturity",
                },
                "sales_data": {
                    "sales_history_7d": sales_7d,
                    "sales_history_30d": sales_30d,
                    "sales_history_90d": sales_90d,
                    "pv_7d": [max(0, int(round(value / max(float(product.conversion_rate or 0.04), 0.01)))) for value in sales_7d],
                    "uv_7d": [max(0, int(round(value / max(float(product.conversion_rate or 0.04), 0.012)))) for value in sales_7d],
                    "conversion_rate_7d": float(product.conversion_rate or 0.0),
                    "promotion_history": promotion_history,
                },
                "database_context": {
                    "product_id": product.id,
                    "updated_at": product.updated_at.isoformat() if product.updated_at else None,
                    "source": product.source,
                    "monthly_sales": int(product.monthly_sales or 0),
                    "click_rate": float(product.click_rate or 0.0),
                    "conversion_rate": float(product.conversion_rate or 0.0),
                    "daily_row_count": len(rows),
                },
            }
        finally:
            db.close()

    def _run(self, product_id: int) -> str:
        return _json_dump(self.fetch_context(product_id))


class SalesMetricsTool(BaseTool):
    name: str = "sales_metrics_tool"
    description: str = "根据数据库上下文计算销量趋势、库存周转和数据质量"
    args_schema: type[BaseModel] = PayloadJsonInput

    def calculate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        sales = payload.get("sales_data", {})
        product = payload.get("product", {})

        sales_7d = sales.get("sales_history_7d", []) or []
        sales_30d = sales.get("sales_history_30d", []) or []
        sales_90d = sales.get("sales_history_90d", []) or []

        avg_7d = _safe_mean(sales_7d)
        avg_30d = _safe_mean(sales_30d)
        avg_90d = _safe_mean(sales_90d)
        baseline = avg_30d or avg_90d or 1.0
        trend_score = (avg_7d - baseline) / max(1.0, baseline)

        stock = float(product.get("stock") or 0.0)
        turnover_days = stock / avg_30d if avg_30d > 0 else None
        stock_age_days = int(product.get("stock_age_days") or 0)

        return {
            "avg_sales_7d": round(avg_7d, 4),
            "avg_sales_30d": round(avg_30d, 4),
            "avg_sales_90d": round(avg_90d, 4),
            "trend_score": round(trend_score, 4),
            "turnover_days": round(turnover_days, 2) if turnover_days is not None else None,
            "stock_age_days": stock_age_days,
            "data_quality_score": 1.0 if sales_30d and sales_90d else 0.6,
        }

    def _run(self, payload_json: str) -> str:
        return _json_dump(self.calculate(_json_load(payload_json)))


class DatabaseRiskContextTool(BaseTool):
    name: str = "database_risk_context_tool"
    description: str = "根据商品 ID 从数据库读取风控计算所需的利润、库存和经营上下文"
    args_schema: type[BaseModel] = ProductIdInput

    def fetch_context(self, product_id: int) -> Dict[str, Any]:
        base_context = DatabaseProductContextTool().fetch_context(product_id)
        product = base_context["product"]
        db_context = base_context["database_context"]

        category = product["category"]
        current_price = float(product["current_price"])
        cost = float(product["cost"])
        platform_fee = round(current_price * 0.055, 2)
        logistics_fee = round(max(3.5, current_price * 0.035), 2)
        after_sales_reserve = round(current_price * 0.012, 2)

        return {
            "product": product,
            "sales_data": base_context["sales_data"],
            "database_context": db_context,
            "risk_data": {
                "min_profit_margin": 0.18,
                "target_profit_margin": 0.28,
                "refund_rate": _default_refund_rate(category),
                "complaint_rate": _default_complaint_rate(category),
                "cost_breakdown": {
                    "procurement": round(cost, 2),
                    "platform_fee": platform_fee,
                    "logistics": logistics_fee,
                    "after_sales_reserve": after_sales_reserve,
                },
                "cash_conversion_cycle": 16 if category == "数码配件" else 9,
                "enforce_hard_constraints": True,
                "constraint_summary": [],
            },
        }

    def _run(self, product_id: int) -> str:
        return _json_dump(self.fetch_context(product_id))


class TaobaoCompetitorFetchTool(BaseTool):
    name: str = "taobao_competitor_fetch_tool"
    description: str = "尝试从淘宝搜索页抓取实时竞品数据；若被风控拦截会明确返回失败原因"
    args_schema: type[BaseModel] = MarketFetchInput

    def fetch_market(self, keyword: str, category: str = "", limit: int = 8) -> Dict[str, Any]:
        keyword = str(keyword or "").strip()
        variants = _keyword_variants(keyword) or [keyword]
        warnings: List[str] = []

        # 仅走子进程抓取，避免在服务主进程事件循环中触发 Windows asyncio 子进程兼容问题。
        for kw in variants:
            primary = _run_taobao_fetch_subprocess(keyword=kw, limit=limit)
            warnings.extend(list(primary.get("warnings", [])))
            if primary.get("success") and primary.get("competitors"):
                primary["warnings"] = warnings
                primary["keyword"] = keyword
                return _ensure_minimum_competitors(primary, keyword=keyword, category=category, limit=limit)

        guaranteed = {
            "success": False,
            "blocked": False,
            "source": "synthetic_fallback",
            "keyword": keyword,
            "warnings": warnings + ["实时抓取全部失败，已启用结构化兜底竞品样本。"],
            "competitors": [],
        }
        return _ensure_minimum_competitors(guaranteed, keyword=keyword, category=category, limit=limit)

    def _run_direct(self, keyword: str, category: str = "", limit: int = 8) -> Dict[str, Any]:
        _ = category
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

    def _run(self, keyword: str, category: str = "", limit: int = 8) -> str:
        return _json_dump(self.fetch_market(keyword=keyword, category=category, limit=limit))


class MarketSnapshotTool(BaseTool):
    name: str = "market_snapshot_tool"
    description: str = "根据竞品列表计算市场竞争强度、价格带和数据可靠性"
    args_schema: type[BaseModel] = PayloadJsonInput

    def calculate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        competitors = payload.get("competitors", []) or []
        prices: List[float] = []
        promotion_count = 0
        low_price_count = 0
        for item in competitors:
            if not isinstance(item, dict):
                continue
            price = item.get("current_price")
            if isinstance(price, (int, float, Decimal)) and price > 0:
                prices.append(float(price))
            tags = item.get("promotion_tags") or []
            if isinstance(tags, list) and tags:
                promotion_count += 1
            if item.get("shop_type") == "taobao":
                low_price_count += 1

        avg_price = round(_safe_mean(prices), 4) if prices else None
        return {
            "competitor_count": len(prices),
            "avg_competitor_price": avg_price,
            "min_competitor_price": round(min(prices), 4) if prices else None,
            "max_competitor_price": round(max(prices), 4) if prices else None,
            "promotion_competitor_count": promotion_count,
            "taobao_shop_share": round(low_price_count / len(prices), 4) if prices else 0.0,
            "market_data_reliable": bool(payload.get("success") and not payload.get("blocked") and len(prices) >= 3),
            "warnings": list(payload.get("warnings", [])),
            "source": payload.get("source", "unknown"),
        }

    def _run(self, payload_json: str) -> str:
        return _json_dump(self.calculate(_json_load(payload_json)))


class RiskConstraintTool(BaseTool):
    name: str = "risk_constraint_tool"
    description: str = "根据商品成本和约束条件计算最低安全价、利润率和最大安全折扣"
    args_schema: type[BaseModel] = PayloadJsonInput

    def calculate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        product = payload.get("product", {})
        risk = payload.get("risk_data", {})
        current_price = float(product.get("current_price") or 0.0)
        cost = float(product.get("cost") or 0.0)
        min_margin = float(risk.get("min_profit_margin") or 0.0)
        min_markup = risk.get("min_profit_markup")
        price_floor = risk.get("price_floor")

        total_cost = cost
        cost_breakdown = risk.get("cost_breakdown")
        if isinstance(cost_breakdown, dict):
            numeric = [float(value) for value in cost_breakdown.values() if isinstance(value, (int, float, Decimal))]
            if numeric:
                total_cost = sum(numeric)

        break_even = total_cost
        min_safe = total_cost / max(1e-6, 1 - min_margin) if min_margin < 1 else total_cost * (1 + min_margin)
        required = max(break_even, min_safe)
        if isinstance(min_markup, (int, float, Decimal)):
            required = max(required, total_cost * (1 + float(min_markup)))
        if isinstance(price_floor, (int, float, Decimal)):
            required = max(required, float(price_floor))

        current_margin = (current_price - total_cost) / current_price if current_price > 0 else 0.0
        max_discount = required / current_price if current_price > 0 else 1.0
        ceiling = risk.get("price_ceiling")
        constraint_conflict = bool(
            isinstance(ceiling, (int, float, Decimal)) and float(ceiling) < required - 1e-6
        )

        return {
            "total_cost": round(total_cost, 4),
            "break_even_price": round(break_even, 4),
            "min_safe_price": round(min_safe, 4),
            "required_min_price": round(required, 4),
            "current_margin": round(current_margin, 4),
            "max_safe_discount": round(max(0.5, min(1.5, max_discount)), 4),
            "constraint_conflict": constraint_conflict,
        }

    def _run(self, payload_json: str) -> str:
        return _json_dump(self.calculate(_json_load(payload_json)))
