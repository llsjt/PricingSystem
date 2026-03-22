"""Local 4-agent pricing logic.

This module implements a deterministic workflow:
1. Data analysis agent
2. Market intelligence agent
3. Risk control agent
4. Manager coordinator agent
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from statistics import mean
from typing import Any, Dict, List, Optional, Sequence

from pricing_crew.config.runtime import settings
from pricing_crew.schemas import (
    AgentSummary,
    AnalysisRequest,
    CompetitorInfo,
    ConflictResolution,
    DataAnalysisResult,
    ExecutionPlan,
    ExpectedOutcomes,
    FinalDecision,
    MarketIntelResult,
    RiskControlResult,
)
from pricing_crew.tools.custom_tool import (
    DatabaseProductContextTool,
    DatabaseRiskContextTool,
    MarketSnapshotTool,
    RiskConstraintTool,
    SalesMetricsTool,
    TaobaoCompetitorFetchTool,
)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _safe_mean(values: Sequence[float | int]) -> float:
    numeric = [float(v) for v in values if isinstance(v, (int, float))]
    if not numeric:
        return 0.0
    return float(mean(numeric))


def _extract_product_id(request: AnalysisRequest) -> Optional[int]:
    try:
        return int(request.product.product_id)
    except (TypeError, ValueError):
        return None


def _load_data_agent_payload(request: AnalysisRequest) -> Dict[str, Any]:
    product_id = _extract_product_id(request)
    prefer_db_tools = bool(request.business_context.get("prefer_db_tools"))
    if prefer_db_tools and product_id is not None:
        payload = DatabaseProductContextTool().fetch_context(product_id)
        payload["tool_trace"] = ["database_product_context_tool", "sales_metrics_tool"]
        return payload

    return {
        "product": request.product.model_dump(mode="json"),
        "sales_data": request.sales_data.model_dump(mode="json"),
        "database_context": {"source": "request_payload"},
        "tool_trace": ["request_payload", "sales_metrics_tool"],
    }


def _load_risk_agent_payload(request: AnalysisRequest) -> Dict[str, Any]:
    product_id = _extract_product_id(request)
    prefer_db_tools = bool(request.business_context.get("prefer_db_tools"))
    if prefer_db_tools and product_id is not None:
        payload = DatabaseRiskContextTool().fetch_context(product_id)
    else:
        payload = {
            "product": request.product.model_dump(mode="json"),
            "sales_data": request.sales_data.model_dump(mode="json"),
            "database_context": request.business_context.get("database_context", {}),
            "risk_data": {},
        }

    merged_risk_data = {**payload.get("risk_data", {}), **request.risk_data.model_dump(mode="json")}
    payload["risk_data"] = merged_risk_data
    payload["tool_trace"] = [
        "database_risk_context_tool" if prefer_db_tools and product_id is not None else "request_payload",
        "risk_constraint_tool",
    ]
    return payload


def _build_market_payload(request: AnalysisRequest) -> Dict[str, Any]:
    if request.competitor_data.competitors:
        return {
            "success": True,
            "blocked": False,
            "source": "request_payload",
            "keyword": request.product.product_name,
            "warnings": [],
            "competitors": [item.model_dump(mode="json") for item in request.competitor_data.competitors],
        }

    tool = TaobaoCompetitorFetchTool()
    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    if running_loop and running_loop.is_running():
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(tool.fetch_market, request.product.product_name, request.product.category, 8)
            return future.result()

    return tool.fetch_market(keyword=request.product.product_name, category=request.product.category, limit=8)


def _demand_elasticity(promotion_history: List[Dict[str, Any]], current_price: float, category: str) -> float:
    points: List[float] = []
    for row in promotion_history:
        before = float(row.get("sales_before") or 0)
        during = float(row.get("sales_during") or 0)
        discount_price = float(row.get("discount_price") or current_price)
        if before <= 0 or discount_price <= 0:
            continue
        price_change = (discount_price - current_price) / max(current_price, 1e-6)
        sales_change = (during - before) / before
        if abs(price_change) > 1e-6:
            points.append(sales_change / price_change)

    if points:
        return round(_clamp(_safe_mean(points), -3.0, 0.0), 4)

    if category == "数码配件":
        return -1.25
    if category == "户外服饰":
        return -1.05
    return -0.82


def _estimate_monthly_sales(request: AnalysisRequest, data_result: Optional[DataAnalysisResult] = None) -> float:
    avg_sales_30d = 0.0
    if data_result is not None:
        avg_sales_30d = float(data_result.analysis_details.get("avg_sales_30d") or 0.0)
    if avg_sales_30d <= 0 and request.sales_data.sales_history_30d:
        avg_sales_30d = _safe_mean(request.sales_data.sales_history_30d)
    if avg_sales_30d <= 0 and request.sales_data.sales_history_7d:
        avg_sales_30d = _safe_mean(request.sales_data.sales_history_7d)
    if avg_sales_30d <= 0 and request.sales_data.sales_history_90d:
        avg_sales_30d = _safe_mean(request.sales_data.sales_history_90d)
    return max(avg_sales_30d * 30.0, 1.0)


def _required_min_price_from_request(request: AnalysisRequest) -> float:
    declared_floor = float(request.risk_data.price_floor) if request.risk_data.price_floor is not None else 0.0
    min_profit_margin = _clamp(float(request.risk_data.min_profit_margin or 0.0), 0.0, 0.95)
    cost = max(float(request.product.cost or 0.0), 0.0)
    margin_floor = cost / max(1.0 - min_profit_margin, 0.05) if cost > 0 else 0.0
    return max(0.01, declared_floor, margin_floor)


def _apply_request_price_bounds(
    request: AnalysisRequest,
    price: float,
    required_min_price: Optional[float] = None,
) -> float:
    normalized = max(float(price), 0.01)
    ceiling = request.risk_data.price_ceiling
    if ceiling is not None:
        normalized = min(normalized, float(ceiling))

    floor = float(required_min_price) if required_min_price is not None else _required_min_price_from_request(request)
    if ceiling is None or float(ceiling) >= floor - 0.01:
        normalized = max(normalized, floor)
    return round(normalized, 2)


def _estimate_sales_lift(current_price: float, suggested_price: float, elasticity: Optional[float]) -> float:
    if current_price <= 0:
        return 1.0
    demand_elasticity = _clamp(float(elasticity if elasticity is not None else -0.9), -3.0, 0.0)
    price_change_ratio = (suggested_price - current_price) / current_price
    expected_sales_change = demand_elasticity * price_change_ratio
    return round(_clamp(1.0 + expected_sales_change, 0.55, 1.8), 3)


def _estimate_profit_change(
    request: AnalysisRequest,
    current_price: float,
    suggested_price: float,
    sales_lift: float,
    elasticity: Optional[float],
    unit_total_cost: Optional[float] = None,
    data_result: Optional[DataAnalysisResult] = None,
) -> float:
    monthly_sales = _estimate_monthly_sales(request, data_result)
    unit_cost = (
        float(unit_total_cost)
        if unit_total_cost is not None
        else float(request.product.cost or 0.0)
    )
    normalized_sales_lift = sales_lift
    if normalized_sales_lift <= 0:
        normalized_sales_lift = _estimate_sales_lift(current_price, suggested_price, elasticity)
    current_profit = (current_price - unit_cost) * monthly_sales
    expected_profit = (suggested_price - unit_cost) * monthly_sales * normalized_sales_lift
    return round(expected_profit - current_profit, 2)


def _candidate_decision(current_price: float, suggested_price: float) -> str:
    if suggested_price > current_price + 0.01:
        return "increase"
    if suggested_price < current_price - 0.01:
        return "discount"
    return "maintain"


def _evaluate_request_candidate(
    request: AnalysisRequest,
    candidate_price: float,
    elasticity: Optional[float],
    required_min_price: Optional[float] = None,
) -> Dict[str, float | str]:
    current_price = max(float(request.product.current_price), 0.01)
    bounded_price = _apply_request_price_bounds(request, candidate_price, required_min_price=required_min_price)
    decision = _candidate_decision(current_price, bounded_price)

    if decision == "maintain":
        return {
            "decision": "maintain",
            "suggested_price": round(current_price, 2),
            "discount_rate": 1.0,
            "sales_lift": 1.0,
            "profit_change": 0.0,
            "market_share_change": 0.0,
        }

    sales_lift = _estimate_sales_lift(current_price, bounded_price, elasticity)
    profit_change = _estimate_profit_change(
        request=request,
        current_price=current_price,
        suggested_price=bounded_price,
        sales_lift=sales_lift,
        elasticity=elasticity,
    )
    market_share_change = round((sales_lift - 1.0) * 0.6, 4)

    return {
        "decision": decision,
        "suggested_price": round(bounded_price, 2),
        "discount_rate": round(bounded_price / current_price, 4),
        "sales_lift": round(sales_lift, 3),
        "profit_change": round(profit_change, 2),
        "market_share_change": market_share_change,
    }


def _pick_best_candidate(
    request: AnalysisRequest,
    candidate_rates: Sequence[float],
    elasticity: Optional[float],
    preferred_decision: Optional[str] = None,
    required_min_price: Optional[float] = None,
) -> Dict[str, float | str]:
    current_price = max(float(request.product.current_price), 0.01)
    by_price: Dict[float, Dict[str, float | str]] = {}

    for raw_rate in candidate_rates:
        try:
            rate = float(raw_rate)
        except (TypeError, ValueError):
            continue
        if rate <= 0:
            continue

        candidate = _evaluate_request_candidate(
            request=request,
            candidate_price=current_price * rate,
            elasticity=elasticity,
            required_min_price=required_min_price,
        )
        key = float(candidate["suggested_price"])
        old = by_price.get(key)
        if old is None or float(candidate["profit_change"]) > float(old["profit_change"]):
            by_price[key] = candidate

    candidates = list(by_price.values())
    if not candidates:
        return {
            "decision": "maintain",
            "suggested_price": round(current_price, 2),
            "discount_rate": 1.0,
            "sales_lift": 1.0,
            "profit_change": 0.0,
            "market_share_change": 0.0,
        }

    def _score(item: Dict[str, float | str]) -> tuple[float, float]:
        return float(item["profit_change"]), -abs(float(item["suggested_price"]) - current_price)

    profitable = [item for item in candidates if str(item["decision"]) != "maintain" and float(item["profit_change"]) > 0]
    if preferred_decision:
        preferred = [item for item in profitable if str(item["decision"]) == preferred_decision]
        if preferred:
            return max(preferred, key=_score)
    if profitable:
        return max(profitable, key=_score)

    maintain = next((item for item in candidates if str(item["decision"]) == "maintain"), None)
    if maintain is not None:
        return maintain
    return max(candidates, key=_score)


def _derive_data_agent_suggested_price(request: AnalysisRequest, result: DataAnalysisResult) -> float:
    action = str(result.recommended_action or "maintain").lower()
    inventory_status = str(result.inventory_status or "normal").lower()
    sales_trend = str(result.sales_trend or "stable").lower()

    candidate_rates: List[float] = [1.0]
    if inventory_status == "severe_overstock":
        candidate_rates.extend([0.9, 0.92, 0.94, 0.96, 0.98])
    elif inventory_status == "overstock" or sales_trend == "declining":
        candidate_rates.extend([0.94, 0.96, 0.98, 0.99, 1.01, 1.02])
    elif inventory_status == "tight" and sales_trend in {"rising", "stable"}:
        candidate_rates.extend([1.01, 1.02, 1.03, 1.04, 1.05])
    elif sales_trend == "rising":
        candidate_rates.extend([1.01, 1.02, 1.03, 1.04])
    else:
        candidate_rates.extend([0.99, 1.01, 1.02, 1.03, 1.04, 1.05])

    try:
        lower_rate, upper_rate = result.recommended_discount_range
        candidate_rates.extend([float(lower_rate), float(upper_rate)])
    except Exception:
        pass

    preferred_decision = "discount" if action in {"discount", "clearance"} else "increase"
    best = _pick_best_candidate(
        request=request,
        candidate_rates=candidate_rates,
        elasticity=result.demand_elasticity,
        preferred_decision=preferred_decision,
    )
    return float(best["suggested_price"])


def _derive_market_agent_suggested_price(request: AnalysisRequest, result: MarketIntelResult) -> float:
    current_price = max(float(request.product.current_price), 0.01)
    market_suggestion = str(result.market_suggestion or "maintain").lower()
    competition_level = str(result.competition_level or "moderate").lower()
    price_position = str(result.price_position or "mid-range").lower()
    avg_price = float(result.avg_competitor_price) if result.avg_competitor_price is not None else None

    candidate_rates: List[float] = [0.99, 1.0, 1.01]
    preferred_decision: Optional[str] = None
    if market_suggestion in {"discount", "penetrate", "price_war"} or (
        price_position == "premium" and competition_level in {"moderate", "fierce"}
    ):
        candidate_rates.extend([0.94, 0.96, 0.97, 0.98, 0.99])
        preferred_decision = "discount"
    elif market_suggestion == "premium" or (price_position == "budget" and competition_level in {"low", "moderate"}):
        candidate_rates.extend([1.01, 1.02, 1.03, 1.05, 1.07])
        preferred_decision = "increase"
    else:
        candidate_rates.extend([0.98, 1.02, 1.03, 1.04])

    if avg_price is not None and current_price > 0:
        anchor_rate = avg_price / current_price
        candidate_rates.extend(
            [anchor_rate * 0.98, anchor_rate * 0.99, anchor_rate, anchor_rate * 1.01, anchor_rate * 1.02]
        )

    elasticity_hint = -1.1 if competition_level == "fierce" else -0.95 if competition_level == "moderate" else -0.8
    best = _pick_best_candidate(
        request=request,
        candidate_rates=candidate_rates,
        elasticity=elasticity_hint,
        preferred_decision=preferred_decision,
    )
    return float(best["suggested_price"])


def _derive_risk_agent_suggested_price(request: AnalysisRequest, result: RiskControlResult) -> float:
    current_price = max(float(request.product.current_price), 0.01)
    price_ceiling = request.risk_data.price_ceiling

    if result.calculation_details.get("constraint_conflict"):
        return round(current_price, 2)
    if result.calculation_details.get("floor_breach"):
        return round(float(result.required_min_price), 2)
    if result.calculation_details.get("ceiling_breach") and price_ceiling is not None:
        return round(float(price_ceiling), 2)

    candidate_rates: List[float] = [1.0, 1.01, 1.02, 1.03]
    if str(result.risk_level or "").lower() == "low":
        candidate_rates.extend([1.04, 1.05])

    if result.allow_promotion:
        candidate_rates.extend([0.99, 0.98, float(result.max_safe_discount or 1.0)])
        preferred_decision = "discount" if str(result.recommendation or "").lower() == "discount" else "increase"
    else:
        preferred_decision = "increase"

    best = _pick_best_candidate(
        request=request,
        candidate_rates=candidate_rates,
        elasticity=-0.8,
        preferred_decision=preferred_decision,
        required_min_price=float(result.required_min_price),
    )
    chosen_price = float(best["suggested_price"])
    if price_ceiling is not None:
        chosen_price = min(chosen_price, float(price_ceiling))
    if price_ceiling is None or float(price_ceiling) >= float(result.required_min_price) - 0.01:
        chosen_price = max(chosen_price, float(result.required_min_price))
    return round(chosen_price, 2)


def run_data_analysis_agent(request: AnalysisRequest) -> DataAnalysisResult:
    payload = _load_data_agent_payload(request)
    metrics = SalesMetricsTool().calculate(payload)
    product = payload["product"]
    sales_data = payload["sales_data"]

    trend_score = float(metrics.get("trend_score") or 0.0)
    turnover_days_value = float(metrics.get("turnover_days") or 999.0)
    stock_age_days = int(product.get("stock_age_days") or 0)

    if trend_score >= 0.18:
        sales_trend = "rising"
    elif trend_score <= -0.18:
        sales_trend = "declining"
    else:
        sales_trend = "stable"

    inventory_health_score = 100.0
    inventory_health_score -= max(0.0, turnover_days_value - 28.0) * 1.35
    inventory_health_score -= max(0, stock_age_days - 45) * 0.28
    inventory_health_score = _clamp(inventory_health_score, 0.0, 100.0)

    if inventory_health_score < 25:
        inventory_status = "severe_overstock"
    elif inventory_health_score < 48:
        inventory_status = "overstock"
    elif inventory_health_score > 88:
        inventory_status = "tight"
    else:
        inventory_status = "normal"

    elasticity = _demand_elasticity(
        promotion_history=sales_data.get("promotion_history", []),
        current_price=float(product.get("current_price") or 0.0),
        category=str(product.get("category") or ""),
    )

    action = "maintain"
    min_rate, max_rate = 1.0, 1.0
    reasons: List[str] = []
    if inventory_status == "severe_overstock" or turnover_days_value >= 75:
        action = "discount"
        min_rate, max_rate = 0.93, 0.96
        reasons.append(f"Inventory pressure is high (turnover_days={turnover_days_value:.1f}).")
    elif inventory_status == "overstock" and sales_trend == "declining":
        action = "discount"
        min_rate, max_rate = 0.95, 0.98
        reasons.append("Demand is weakening while inventory is elevated.")
    elif inventory_status == "tight" and sales_trend == "rising":
        reasons.append("Demand and stock indicate no need for discounting.")
    else:
        reasons.append("Demand and inventory are relatively stable.")

    confidence = _clamp(0.55 + abs(trend_score) * 0.3 + (0.08 if sales_data.get("promotion_history") else 0.0), 0.35, 0.86)
    limitations: List[str] = []
    if payload["tool_trace"][0] != "database_product_context_tool":
        limitations.append("Data agent used request payload instead of database context.")
    if float(metrics.get("data_quality_score") or 1.0) < 1.0:
        limitations.append("Sales history is incomplete; confidence is reduced.")

    base_result = DataAnalysisResult(
        sales_trend=sales_trend,
        sales_trend_score=round(trend_score, 4),
        inventory_status=inventory_status,
        inventory_health_score=round(inventory_health_score, 2),
        estimated_turnover_days=int(turnover_days_value) if turnover_days_value < 999 else None,
        demand_elasticity=elasticity,
        demand_elasticity_confidence=0.7 if sales_data.get("promotion_history") else 0.45,
        product_lifecycle_stage=str(product.get("product_lifecycle_stage") or "maturity"),
        lifecycle_evidence="Derived from sales window and product context.",
        has_anomalies=False,
        anomaly_list=[],
        recommended_action=action,
        recommended_discount_range=(min_rate, max_rate),
        recommendation_confidence=round(confidence, 4),
        recommendation_reasons=reasons,
        analysis_details={
            "avg_sales_7d": metrics.get("avg_sales_7d"),
            "avg_sales_30d": metrics.get("avg_sales_30d"),
            "avg_sales_90d": metrics.get("avg_sales_90d"),
            "tool_trace": payload["tool_trace"],
            "data_source": payload["database_context"].get("source", "request_payload"),
        },
        data_quality_score=float(metrics.get("data_quality_score") or 1.0),
        limitations=limitations,
        thinking_process="Used sales_metrics_tool on product/sales context, then inferred trend and inventory pressure.",
        reasoning=(
            f"avg_7d={float(metrics.get('avg_sales_7d') or 0):.2f}, "
            f"avg_30d={float(metrics.get('avg_sales_30d') or 0):.2f}, "
            f"trend={trend_score:.2f}, turnover_days={turnover_days_value:.1f}."
        ),
        decision_summary=f"Data analysis suggests '{action}' with rate range {min_rate:.2f}-{max_rate:.2f}.",
        confidence=round(confidence, 4),
    )

    suggested_price = _derive_data_agent_suggested_price(request, base_result)
    sales_lift = _estimate_sales_lift(float(request.product.current_price), suggested_price, base_result.demand_elasticity)
    expected_profit_change = _estimate_profit_change(
        request=request,
        current_price=float(request.product.current_price),
        suggested_price=suggested_price,
        sales_lift=sales_lift,
        elasticity=base_result.demand_elasticity,
        data_result=base_result,
    )
    return base_result.model_copy(
        update={
            "suggested_price": round(suggested_price, 2),
            "expected_profit_change": round(expected_profit_change, 2),
        }
    )


def run_market_intel_agent(request: AnalysisRequest) -> MarketIntelResult:
    market_payload = _build_market_payload(request)
    market_metrics = MarketSnapshotTool().calculate(market_payload)

    competitors: List[CompetitorInfo] = [
        CompetitorInfo(
            competitor_id=str(item.get("competitor_id") or f"COMP_{idx}"),
            product_name=str(item.get("product_name") or item.get("title") or ""),
            current_price=float(item.get("current_price") or 0.0),
            original_price=float(item["original_price"]) if item.get("original_price") is not None else None,
            sales_volume=int(item.get("sales_volume") or 0) if item.get("sales_volume") is not None else None,
            rating=float(item.get("rating") or 0.0) if item.get("rating") is not None else None,
            review_count=int(item.get("review_count") or 0) if item.get("review_count") is not None else None,
            shop_type=str(item.get("shop_type") or "") if item.get("shop_type") is not None else None,
            is_self_operated=bool(item.get("is_self_operated")),
            promotion_tags=list(item.get("promotion_tags") or []),
        )
        for idx, item in enumerate(market_payload.get("competitors", []), start=1)
    ]

    current_price = float(request.product.current_price)
    prices = [item.current_price for item in competitors if item.current_price > 0]
    competitor_count = max(int(market_metrics.get("competitor_count") or 0), len(prices))
    promotion_count = int(market_metrics.get("promotion_competitor_count") or 0)
    competition_score = _clamp(competitor_count / 12.0 + promotion_count / max(1, competitor_count) * 0.35, 0.0, 1.0)
    if competition_score >= 0.7:
        competition_level = "fierce"
    elif competition_score >= 0.35:
        competition_level = "moderate"
    else:
        competition_level = "low"

    avg_price = float(market_metrics["avg_competitor_price"]) if market_metrics.get("avg_competitor_price") is not None else None
    min_price = float(market_metrics["min_competitor_price"]) if market_metrics.get("min_competitor_price") is not None else None
    max_price = float(market_metrics["max_competitor_price"]) if market_metrics.get("max_competitor_price") is not None else None

    if prices:
        lower_count = sum(1 for value in prices if value < current_price)
        price_percentile = lower_count / len(prices)
        price_gap = (current_price - (avg_price or current_price)) / max((avg_price or current_price), 1e-6)
    else:
        price_percentile = 0.5
        price_gap = None

    if avg_price is None:
        price_position = "mid-range"
    elif current_price >= avg_price * 1.08:
        price_position = "premium"
    elif current_price <= avg_price * 0.92:
        price_position = "budget"
    else:
        price_position = "mid-range"

    live_market_available = bool(market_metrics.get("market_data_reliable"))
    suggestion = "maintain"
    reasons: List[str] = []
    limitations = [str(item) for item in list(market_payload.get("warnings", [])) if item]
    if not live_market_available:
        if market_payload.get("blocked"):
            limitations.append("Market fetch was blocked or unavailable.")
        if not limitations:
            limitations.append("No reliable competitor sample for this request.")
        reasons.append("Market data is not reliable; avoid aggressive discounting.")
        confidence = 0.32
    else:
        if price_position == "premium" and competition_level == "fierce":
            suggestion = "discount"
            reasons.append("Price is premium under fierce competition.")
        elif price_position == "budget" and competition_level == "low":
            suggestion = "premium"
            reasons.append("Current price is budget under weak competition.")
        else:
            reasons.append("Current price band is close to peers.")
        confidence = _clamp(0.48 + competition_score * 0.25, 0.42, 0.82)

    base_result = MarketIntelResult(
        competition_level=competition_level,
        competition_score=round(competition_score, 4),
        price_position=price_position,
        price_percentile=round(price_percentile, 4),
        min_competitor_price=min_price,
        max_competitor_price=max_price,
        avg_competitor_price=avg_price,
        price_gap_vs_avg=round(price_gap, 4) if price_gap is not None else None,
        active_competitor_promotions=[
            {
                "competitor_id": item.competitor_id,
                "competitor_name": item.product_name,
                "promotion_tags": item.promotion_tags,
                "current_price": item.current_price,
            }
            for item in competitors
            if item.promotion_tags
        ][:10],
        upcoming_events=request.competitor_data.upcoming_platform_events,
        sentiment_score=0.0,
        sentiment_label="neutral",
        top_positive_keywords=[],
        top_negative_keywords=[],
        estimated_market_share=None,
        market_share_trend=None,
        market_suggestion=suggestion,
        suggestion_confidence=round(confidence, 4),
        suggestion_reasons=reasons,
        analysis_details={
            "tool_trace": ["simulated_competitor_dataset_tool", "market_snapshot_tool"],
            "live_market_available": live_market_available,
            "market_source": market_payload.get("source", "unknown"),
            "competitor_count": len(competitors),
            "fetch_failed": not live_market_available,
            "failure_reasons": limitations if not live_market_available else [],
        },
        data_sources=[str(market_payload.get("source", "unknown"))],
        limitations=limitations,
        thinking_process="Generated competitor sample, then evaluated positioning and competition pressure.",
        reasoning=(
            f"competitors={len(competitors)}, avg_comp_price={avg_price if avg_price is not None else 'unknown'}, "
            f"price_percentile={price_percentile:.2f}, live_market_available={live_market_available}."
        ),
        decision_summary=f"Market intel suggests '{suggestion}'.",
        confidence=round(confidence, 4),
    )

    suggested_price = _derive_market_agent_suggested_price(request, base_result)
    elasticity_hint = -1.1 if competition_level == "fierce" else -0.95 if competition_level == "moderate" else -0.8
    sales_lift = _estimate_sales_lift(float(request.product.current_price), suggested_price, elasticity_hint)
    expected_profit_change = _estimate_profit_change(
        request=request,
        current_price=float(request.product.current_price),
        suggested_price=suggested_price,
        sales_lift=sales_lift,
        elasticity=elasticity_hint,
    )
    return base_result.model_copy(
        update={
            "suggested_price": round(suggested_price, 2),
            "expected_profit_change": round(expected_profit_change, 2),
        }
    )


def run_risk_control_agent(request: AnalysisRequest) -> RiskControlResult:
    payload = _load_risk_agent_payload(request)
    calc = RiskConstraintTool().calculate(payload)
    product = payload["product"]
    risk = payload["risk_data"]

    current_price = float(product.get("current_price") or 0.0)
    required_min_price = float(calc["required_min_price"])
    price_ceiling = risk.get("price_ceiling")
    ceiling_breach = bool(price_ceiling is not None and current_price > float(price_ceiling) + 1e-6)
    floor_breach = current_price + 1e-6 < required_min_price
    constraint_conflict = bool(calc.get("constraint_conflict"))
    stock_age_days = int(product.get("stock_age_days") or 0)

    current_margin = float(calc["current_margin"])
    refund_rate = float(risk.get("refund_rate") or 0.0)
    complaint_rate = float(risk.get("complaint_rate") or 0.0)

    profit_risk = 85 if floor_breach else 60 if current_margin < float(risk.get("min_profit_margin") or 0.18) else 22
    stock_risk = 72 if stock_age_days >= 120 else 50 if stock_age_days >= 80 else 18
    refund_risk = _clamp(refund_rate * 650, 0.0, 100.0)
    complaint_risk = _clamp(complaint_rate * 1300, 0.0, 100.0)
    conflict_risk = 95 if constraint_conflict else 0
    risk_score = round(
        profit_risk * 0.34 + stock_risk * 0.22 + refund_risk * 0.18 + complaint_risk * 0.12 + conflict_risk * 0.14,
        2,
    )
    if risk_score >= 70:
        risk_level = "high"
    elif risk_score >= 40:
        risk_level = "medium"
    else:
        risk_level = "low"

    current_price_compliant = not floor_breach and not ceiling_breach and not constraint_conflict
    max_safe_discount = max(float(calc["max_safe_discount"]), float(risk.get("max_discount_allowed") or 0.0))
    max_safe_discount = round(_clamp(max_safe_discount, 0.5, 1.0), 4)

    warnings: List[str] = []
    reasons = [
        f"required_min_price={required_min_price:.2f}",
        f"current_margin={current_margin:.1%}",
        f"risk_score={risk_score:.2f}",
    ]
    if refund_rate > 0.05:
        warnings.append(f"High refund rate ({refund_rate:.1%}).")
    if complaint_rate > 0.01:
        warnings.append(f"High complaint rate ({complaint_rate:.1%}).")
    if stock_age_days >= 90:
        warnings.append(f"High stock age ({stock_age_days} days).")
    if constraint_conflict:
        warnings.append("Price constraints conflict with required minimum safe price.")

    recommendation = "maintain"
    veto_reason: Optional[str] = None
    allow_promotion = False
    if constraint_conflict:
        recommendation = "maintain"
        veto_reason = "Constraint conflict must be resolved before automatic pricing."
    elif floor_breach:
        recommendation = "increase"
        veto_reason = f"Current price {current_price:.2f} is below safe minimum {required_min_price:.2f}."
    elif ceiling_breach:
        recommendation = "discount"
        allow_promotion = True
    else:
        allow_promotion = risk_level != "high" and max_safe_discount < 1.0
        recommendation = "discount" if allow_promotion else "maintain"
        if not allow_promotion:
            veto_reason = "Risk posture does not support proactive discounting."

    discounted_price = max(current_price * max_safe_discount, 0.01)
    unit_total_cost = float(calc["total_cost"])
    profit_margin_after_discount = (
        (discounted_price - unit_total_cost) / discounted_price if discounted_price > 0 else 0.0
    )

    base_result = RiskControlResult(
        current_profit_margin=round(current_margin, 4),
        profit_margin_after_discount=round(profit_margin_after_discount, 4),
        break_even_price=float(calc["break_even_price"]),
        min_safe_price=float(calc["min_safe_price"]),
        required_min_price=required_min_price,
        absolute_price_floor=float(risk["price_floor"]) if risk.get("price_floor") is not None else None,
        current_price_compliant=current_price_compliant,
        risk_level=risk_level,
        risk_score=risk_score,
        risk_breakdown={
            "profit_risk": round(profit_risk, 2),
            "stock_risk": round(stock_risk, 2),
            "refund_risk": round(refund_risk, 2),
            "complaint_risk": round(complaint_risk, 2),
            "constraint_conflict": round(conflict_risk, 2),
        },
        allow_promotion=allow_promotion,
        max_safe_discount=max_safe_discount,
        discount_conditions=[] if allow_promotion else ["No proactive discounting under current risk constraints."],
        warnings=warnings,
        recommendation=recommendation,
        recommendation_reasons=reasons,
        constraint_summary=list(risk.get("constraint_summary") or []),
        calculation_details={
            "tool_trace": payload["tool_trace"],
            "price_ceiling": float(price_ceiling) if price_ceiling is not None else None,
            "constraint_conflict": constraint_conflict,
            "ceiling_breach": ceiling_breach,
            "floor_breach": floor_breach,
            "total_cost": unit_total_cost,
        },
        compliance_check=current_price_compliant,
        veto_reason=veto_reason,
        thinking_process="Computed hard constraints first, then aggregated operational risk factors.",
        reasoning=(
            f"total_cost={unit_total_cost:.2f}, required_min_price={required_min_price:.2f}, "
            f"price_ceiling={price_ceiling if price_ceiling is not None else 'none'}, risk_level={risk_level}."
        ),
        decision_summary=f"Risk control suggests '{recommendation}'.",
        confidence=round(_clamp(1.0 - risk_score / 120.0, 0.2, 0.92), 4),
    )

    suggested_price = _derive_risk_agent_suggested_price(request, base_result)
    sales_lift = _estimate_sales_lift(float(request.product.current_price), suggested_price, -0.8)
    expected_profit_change = _estimate_profit_change(
        request=request,
        current_price=float(request.product.current_price),
        suggested_price=suggested_price,
        sales_lift=sales_lift,
        elasticity=-0.8,
        unit_total_cost=unit_total_cost,
    )
    return base_result.model_copy(
        update={
            "suggested_price": round(suggested_price, 2),
            "expected_profit_change": round(expected_profit_change, 2),
        }
    )


def _evaluate_agent_price(
    request: AnalysisRequest,
    data_result: DataAnalysisResult,
    risk_result: RiskControlResult,
    proposed_price: float,
) -> Dict[str, float | str]:
    current_price = max(float(request.product.current_price), 0.01)
    price_ceiling = request.risk_data.price_ceiling
    required_min_price = float(risk_result.required_min_price)
    has_constraint_conflict = bool(risk_result.calculation_details.get("constraint_conflict"))

    evaluated_price = round(float(proposed_price), 2)
    if price_ceiling is not None:
        evaluated_price = min(evaluated_price, float(price_ceiling))
    if not has_constraint_conflict and (price_ceiling is None or float(price_ceiling) >= required_min_price - 0.01):
        evaluated_price = max(evaluated_price, required_min_price)
    evaluated_price = round(max(evaluated_price, 0.01), 2)

    decision = _candidate_decision(current_price, evaluated_price)
    if decision == "maintain":
        return {
            "decision": "maintain",
            "suggested_price": round(current_price, 2),
            "discount_rate": 1.0,
            "sales_lift": 1.0,
            "profit_change": 0.0,
            "market_share_change": 0.0,
        }

    sales_lift = _estimate_sales_lift(current_price, evaluated_price, data_result.demand_elasticity)
    unit_total_cost = float(risk_result.calculation_details.get("total_cost") or request.product.cost or 0.0)
    profit_change = _estimate_profit_change(
        request=request,
        current_price=current_price,
        suggested_price=evaluated_price,
        sales_lift=sales_lift,
        elasticity=data_result.demand_elasticity,
        unit_total_cost=unit_total_cost,
        data_result=data_result,
    )
    if decision == "discount":
        market_share_change = round(max(0.0, 1.0 - evaluated_price / current_price) * 0.18, 4)
    else:
        market_share_change = round((sales_lift - 1.0) * 0.6, 4)

    return {
        "decision": decision,
        "suggested_price": round(evaluated_price, 2),
        "discount_rate": round(evaluated_price / current_price, 4),
        "sales_lift": round(sales_lift, 3),
        "profit_change": round(profit_change, 2),
        "market_share_change": market_share_change,
    }


def _build_price_conflicts(evaluated_proposals: List[Dict[str, Any]], current_price: float) -> List[ConflictResolution]:
    conflicts: List[ConflictResolution] = []

    increase_items = [item for item in evaluated_proposals if str(item.get("decision")) == "increase"]
    discount_items = [item for item in evaluated_proposals if str(item.get("decision")) == "discount"]
    if increase_items and discount_items:
        top_inc = max(increase_items, key=lambda item: float(item.get("profit_change", 0.0)))
        top_dec = max(discount_items, key=lambda item: float(item.get("profit_change", 0.0)))
        conflicts.append(
            ConflictResolution(
                agent1=str(top_inc.get("agent_name", "data")),
                agent2=str(top_dec.get("agent_name", "market")),
                conflict="Direction conflict between increase and discount proposals.",
                resolution="Manager compares both directions using profit and constraints, then selects one.",
                priority="manager",
            )
        )

    prices = [float(item.get("suggested_price", current_price)) for item in evaluated_proposals]
    if prices and current_price > 0:
        spread_ratio = (max(prices) - min(prices)) / current_price
        if spread_ratio >= 0.03:
            conflicts.append(
                ConflictResolution(
                    agent1="team",
                    agent2="team",
                    conflict=f"Proposal spread is high ({spread_ratio:.1%}).",
                    resolution="Manager adds a midpoint proposal and re-evaluates profitability.",
                    priority="manager",
                )
            )
    return conflicts


def _manager_revision_prices(current_price: float, base_prices: Sequence[float]) -> List[float]:
    revision_rates = [0.97, 0.98, 0.99, 1.01, 1.02, 1.03, 1.04, 1.05, 1.06]
    revisions = [current_price * rate for rate in revision_rates]
    if base_prices:
        revisions.append(sum(base_prices) / len(base_prices))
        revisions.append((min(base_prices) + max(base_prices)) / 2)
    return sorted({round(v, 2) for v in revisions if v > 0})


def run_manager_coordinator_agent(
    request: AnalysisRequest,
    data_result: DataAnalysisResult,
    market_result: MarketIntelResult,
    risk_result: RiskControlResult,
) -> FinalDecision:
    current_price = max(float(request.product.current_price), 0.01)
    price_ceiling = request.risk_data.price_ceiling
    strategy_goal = (request.strategy_goal or "MAX_PROFIT").upper()
    market_live_available = bool(market_result.analysis_details.get("live_market_available"))
    warnings = list(risk_result.warnings[:3])

    data_price = float(data_result.suggested_price or _derive_data_agent_suggested_price(request, data_result))
    market_price = float(market_result.suggested_price or _derive_market_agent_suggested_price(request, market_result))
    risk_price = float(risk_result.suggested_price or _derive_risk_agent_suggested_price(request, risk_result))
    proposals: List[tuple[str, float]] = [
        ("data", data_price),
        ("market", market_price),
        ("risk", risk_price),
    ]

    unique_prices = sorted({round(price, 2) for _, price in proposals})
    if len(unique_prices) >= 2:
        proposals.append(("manager_midpoint", round((unique_prices[0] + unique_prices[-1]) / 2, 2)))

    evaluated_proposals: List[Dict[str, Any]] = []
    for agent_name, proposed_price in proposals:
        evaluated = _evaluate_agent_price(request, data_result, risk_result, proposed_price)
        evaluated["agent_name"] = agent_name
        evaluated_proposals.append(evaluated)

    conflicts = _build_price_conflicts(evaluated_proposals, current_price)
    mandatory_move = bool(
        risk_result.calculation_details.get("floor_breach")
        or (risk_result.calculation_details.get("ceiling_breach") and price_ceiling is not None)
    )

    if risk_result.calculation_details.get("constraint_conflict"):
        chosen = {
            "agent_name": "manager",
            "decision": "maintain",
            "suggested_price": round(current_price, 2),
            "discount_rate": 1.0,
            "sales_lift": 1.0,
            "profit_change": 0.0,
            "market_share_change": 0.0,
        }
        key_factors = ["constraint_conflict", "manual_review"]
        warnings.append("Constraint conflict prevents safe automatic repricing.")
    elif mandatory_move:
        forced_price = float(risk_result.required_min_price)
        if risk_result.calculation_details.get("ceiling_breach") and price_ceiling is not None:
            forced_price = float(price_ceiling)
        chosen = _evaluate_agent_price(request, data_result, risk_result, forced_price)
        chosen["agent_name"] = "risk"
        key_factors = ["risk_boundary", "forced_adjustment"]
    else:
        key_factors = ["three_agent_proposals", "manager_coordination", "profit_validation"]
        candidate_pool = list(evaluated_proposals)
        if settings.market_live_required_for_discount and not market_live_available:
            candidate_pool = [item for item in candidate_pool if str(item["decision"]) != "discount"]
            warnings.append("Discount proposals were downweighted because live market data is unavailable.")

        profitable = [
            item
            for item in candidate_pool
            if str(item["decision"]) != "maintain" and float(item["profit_change"]) > 0
        ]

        if strategy_goal == "MAX_PROFIT" and not profitable:
            for price in _manager_revision_prices(current_price, [data_price, market_price, risk_price]):
                revised = _evaluate_agent_price(request, data_result, risk_result, price)
                revised["agent_name"] = "manager_revision"
                evaluated_proposals.append(revised)
                if not (settings.market_live_required_for_discount and not market_live_available and str(revised["decision"]) == "discount"):
                    candidate_pool.append(revised)
            profitable = [
                item
                for item in candidate_pool
                if str(item["decision"]) != "maintain" and float(item["profit_change"]) > 0
            ]

        if strategy_goal == "MAX_PROFIT":
            if profitable:
                chosen = max(
                    profitable,
                    key=lambda item: (
                        float(item["profit_change"]),
                        -abs(float(item["suggested_price"]) - current_price),
                    ),
                )
            else:
                chosen = {
                    "agent_name": "manager",
                    "decision": "maintain",
                    "suggested_price": round(current_price, 2),
                    "discount_rate": 1.0,
                    "sales_lift": 1.0,
                    "profit_change": 0.0,
                    "market_share_change": 0.0,
                }
                warnings.append("No executable price adjustment improves expected profit under current constraints.")
        elif strategy_goal == "CLEARANCE":
            non_negative = [item for item in candidate_pool if float(item["profit_change"]) >= 0]
            chosen = min(non_negative or candidate_pool, key=lambda item: float(item["suggested_price"]))
        elif strategy_goal == "MARKET_SHARE":
            non_negative = [item for item in candidate_pool if float(item["profit_change"]) >= 0]
            chosen = max(
                non_negative or candidate_pool,
                key=lambda item: (float(item["market_share_change"]), float(item["profit_change"])),
            )
        else:
            non_negative = [item for item in candidate_pool if float(item["profit_change"]) >= 0]
            chosen = max(
                non_negative or candidate_pool,
                key=lambda item: (float(item["profit_change"]), -abs(float(item["suggested_price"]) - current_price)),
            )

    final_decision = str(chosen["decision"])
    final_price = float(chosen["suggested_price"])
    expected_outcomes = ExpectedOutcomes(
        sales_lift=float(chosen["sales_lift"]),
        profit_change=float(chosen["profit_change"]),
        market_share_change=float(chosen["market_share_change"]),
    )

    proposal_text = "; ".join(
        f"{item['agent_name']}={float(item['suggested_price']):.2f}(delta {float(item['profit_change']):.2f})"
        for item in evaluated_proposals[:8]
    )
    core_reasons = (
        "Manager coordinated independent proposals from data/market/risk agents, "
        f"resolved conflicts, and selected '{chosen['agent_name']}'. {proposal_text}"
    )

    confidence = _clamp(
        (data_result.recommendation_confidence + market_result.suggestion_confidence + risk_result.confidence) / 3,
        0.28,
        0.88,
    )
    if not market_live_available:
        confidence = min(confidence, 0.56)
    if risk_result.calculation_details.get("constraint_conflict"):
        confidence = min(confidence, 0.3)

    conflict_summary = "; ".join(item.resolution for item in conflicts)
    report_text = (
        "thinking: manager compared independent agent proposals and checked constraints\n"
        f"reasoning: {core_reasons}\n"
        f"decision: {final_decision}, suggested_price={final_price:.2f}\n"
        f"conflicts: {conflict_summary or 'none'}"
    )

    return FinalDecision(
        decision=final_decision,
        discount_rate=round(float(chosen["discount_rate"]), 4),
        suggested_price=round(final_price, 2),
        confidence=round(confidence, 4),
        expected_outcomes=expected_outcomes,
        core_reasons=core_reasons,
        key_factors=key_factors,
        conflicts_detected=conflicts,
        risk_warning=risk_result.veto_reason or ("risk acceptable" if risk_result.allow_promotion else "risk constrained"),
        contingency_plan="Rollback if conversion, margin, or refund profile deteriorates within 24h.",
        execution_plan=[
            ExecutionPlan(step=1, action=f"Apply price {final_price:.2f}", timing="immediately", responsible="ops"),
            ExecutionPlan(step=2, action="Monitor conversion, gross margin, refund rate", timing="24h", responsible="analyst"),
        ],
        report_text=report_text,
        agent_summaries=[
            AgentSummary(agent_name="data", summary=data_result.decision_summary, key_points=data_result.recommendation_reasons[:3]),
            AgentSummary(agent_name="market", summary=market_result.decision_summary, key_points=market_result.suggestion_reasons[:3]),
            AgentSummary(agent_name="risk", summary=risk_result.decision_summary, key_points=risk_result.recommendation_reasons[:3]),
        ],
        decision_framework="three business agents propose; manager coordinates and arbitrates",
        alternative_options=[
            {"option": "keep_current_price", "discount_rate": 1.0},
            {"option": "risk_min_price", "discount_rate": round(float(risk_result.required_min_price) / current_price, 4)},
        ],
        thinking_process="Each business agent proposes first; manager resolves conflicts and selects final price.",
        reasoning=core_reasons,
        conflict_summary=conflict_summary,
        warnings=warnings,
        agent_summaries_structured={
            "dataAnalysis": {
                "salesTrend": data_result.sales_trend,
                "inventoryStatus": data_result.inventory_status,
                "suggestedPrice": round(data_price, 2),
                "expectedProfitChange": data_result.expected_profit_change,
            },
            "marketIntel": {
                "competitionLevel": market_result.competition_level,
                "pricePosition": market_result.price_position,
                "suggestedPrice": round(market_price, 2),
                "expectedProfitChange": market_result.expected_profit_change,
                "liveMarketAvailable": market_live_available,
            },
            "riskControl": {
                "riskLevel": risk_result.risk_level,
                "requiredMinPrice": risk_result.required_min_price,
                "suggestedPrice": round(risk_price, 2),
                "expectedProfitChange": risk_result.expected_profit_change,
                "allowPromotion": risk_result.allow_promotion,
            },
        },
    )
