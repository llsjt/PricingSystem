from __future__ import annotations

import json
from statistics import mean
from typing import Any, Dict, List

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class RequestJsonInput(BaseModel):
    request_json: str = Field(..., description="Serialized AnalysisRequest JSON.")


def _load_payload(request_json: str) -> Dict[str, Any]:
    try:
        payload = json.loads(request_json)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _safe_mean(values: List[float]) -> float:
    clean = [float(v) for v in values if isinstance(v, (int, float))]
    if not clean:
        return 0.0
    return float(mean(clean))


class SalesMetricsTool(BaseTool):
    name: str = "sales_metrics_tool"
    description: str = (
        "Compute quick sales and inventory metrics from request_json, including average sales and turnover days."
    )
    args_schema: type[BaseModel] = RequestJsonInput

    def _run(self, request_json: str) -> str:
        payload = _load_payload(request_json)
        product = payload.get("product", {})
        sales_data = payload.get("sales_data", {})

        sales_7d = sales_data.get("sales_history_7d", []) or []
        sales_30d = sales_data.get("sales_history_30d", []) or []
        sales_90d = sales_data.get("sales_history_90d", []) or []

        avg_7d = _safe_mean(sales_7d)
        avg_30d = _safe_mean(sales_30d)
        avg_90d = _safe_mean(sales_90d)

        stock = float(product.get("stock") or 0)
        turnover_days = stock / avg_30d if avg_30d > 0 else None

        result = {
            "avg_sales_7d": round(avg_7d, 4),
            "avg_sales_30d": round(avg_30d, 4),
            "avg_sales_90d": round(avg_90d, 4),
            "turnover_days": round(turnover_days, 2) if turnover_days is not None else None,
        }
        return json.dumps(result, ensure_ascii=False)


class MarketSnapshotTool(BaseTool):
    name: str = "market_snapshot_tool"
    description: str = (
        "Summarize competitor prices and promotion counts from request_json to support market intel decisions."
    )
    args_schema: type[BaseModel] = RequestJsonInput

    def _run(self, request_json: str) -> str:
        payload = _load_payload(request_json)
        competitors = (
            payload.get("competitor_data", {}).get("competitors", [])
            if isinstance(payload.get("competitor_data"), dict)
            else []
        )
        prices: List[float] = []
        promo_count = 0

        for competitor in competitors:
            if not isinstance(competitor, dict):
                continue
            current_price = competitor.get("current_price")
            if isinstance(current_price, (int, float)) and current_price > 0:
                prices.append(float(current_price))
            tags = competitor.get("promotion_tags") or []
            if isinstance(tags, list) and tags:
                promo_count += 1

        result = {
            "competitor_count": len(prices),
            "avg_competitor_price": round(_safe_mean(prices), 4) if prices else None,
            "min_competitor_price": round(min(prices), 4) if prices else None,
            "max_competitor_price": round(max(prices), 4) if prices else None,
            "promotion_competitor_count": promo_count,
        }
        return json.dumps(result, ensure_ascii=False)


class RiskConstraintTool(BaseTool):
    name: str = "risk_constraint_tool"
    description: str = (
        "Calculate deterministic risk guardrails (required minimum price and max safe discount) from request_json."
    )
    args_schema: type[BaseModel] = RequestJsonInput

    def _run(self, request_json: str) -> str:
        payload = _load_payload(request_json)
        product = payload.get("product", {})
        risk_data = payload.get("risk_data", {})

        current_price = float(product.get("current_price") or 0.0)
        cost = float(product.get("cost") or 0.0)
        min_profit_margin = float(risk_data.get("min_profit_margin") or 0.0)
        min_profit_markup = risk_data.get("min_profit_markup")
        price_floor = risk_data.get("price_floor")

        break_even_price = cost
        min_safe_price = cost / max(1e-6, (1 - min_profit_margin)) if min_profit_margin < 1 else cost * (1 + min_profit_margin)
        required_min_price = max(break_even_price, min_safe_price)

        if isinstance(min_profit_markup, (int, float)):
            required_min_price = max(required_min_price, cost * (1 + float(min_profit_markup)))

        if isinstance(price_floor, (int, float)):
            required_min_price = max(required_min_price, float(price_floor))

        max_safe_discount = required_min_price / current_price if current_price > 0 else 1.0
        max_safe_discount = max(0.5, min(1.5, max_safe_discount))

        result = {
            "break_even_price": round(break_even_price, 4),
            "min_safe_price": round(min_safe_price, 4),
            "required_min_price": round(required_min_price, 4),
            "max_safe_discount": round(max_safe_discount, 4),
        }
        return json.dumps(result, ensure_ascii=False)
