"""四智能体本地规则实现，按真实业务工具链顺序生成定价建议。"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from statistics import mean
from typing import Any, Dict, List, Optional

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


def _safe_mean(values: List[float]) -> float:
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
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
    payload["tool_trace"] = ["database_risk_context_tool" if prefer_db_tools and product_id is not None else "request_payload", "risk_constraint_tool"]
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
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                tool.fetch_market,
                request.product.product_name,
                request.product.category,
                8,
            )
            return future.result()

    return tool.fetch_market(
        keyword=request.product.product_name,
        category=request.product.category,
        limit=8,
    )


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


def run_data_analysis_agent(request: AnalysisRequest) -> DataAnalysisResult:
    payload = _load_data_agent_payload(request)
    metrics = SalesMetricsTool().calculate(payload)
    product = payload["product"]
    sales_data = payload["sales_data"]

    trend_score = float(metrics["trend_score"])
    turnover_days = metrics.get("turnover_days") or 999.0
    stock_age_days = int(product.get("stock_age_days") or 0)

    if trend_score >= 0.18:
        sales_trend = "rising"
    elif trend_score <= -0.18:
        sales_trend = "declining"
    else:
        sales_trend = "stable"

    inventory_health_score = 100.0
    inventory_health_score -= max(0.0, float(turnover_days) - 28.0) * 1.35
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
    min_rate = 1.0
    max_rate = 1.0
    reasons: List[str] = []

    if inventory_status == "severe_overstock" or turnover_days >= 75:
        action = "discount"
        min_rate, max_rate = 0.93, 0.96
        reasons.append(f"库存周转天数约 {turnover_days:.1f} 天，库存压力过高。")
    elif inventory_status == "overstock" and sales_trend == "declining":
        action = "discount"
        min_rate, max_rate = 0.95, 0.98
        reasons.append("销量走弱且库存偏高，适合小幅测试降价。")
    elif inventory_status == "tight" and sales_trend == "rising":
        reasons.append("销量向上且库存偏紧，不建议贸然降价。")
    else:
        reasons.append("销量与库存信号总体平稳，优先维持当前价格。")

    confidence = _clamp(0.55 + abs(trend_score) * 0.3 + (0.08 if sales_data.get("promotion_history") else 0.0), 0.35, 0.86)
    limitations: List[str] = []
    if payload["tool_trace"][0] != "database_product_context_tool":
        limitations.append("当前结果直接使用请求载荷，未走数据库校验。")
    if metrics["data_quality_score"] < 1.0:
        limitations.append("近 90 天经营数据不完整，建议补齐后再做正式决策。")

    thinking = "先从数据库读取商品和经营数据，再通过销量计算工具评估趋势、周转和库存健康度。"
    reasoning = (
        f"近 7 天均销 {metrics['avg_sales_7d']:.2f}，近 30 天均销 {metrics['avg_sales_30d']:.2f}，"
        f"趋势得分 {trend_score:.2f}，库存周转 {turnover_days:.1f} 天。"
    )

    return DataAnalysisResult(
        sales_trend=sales_trend,
        sales_trend_score=round(trend_score, 4),
        inventory_status=inventory_status,
        inventory_health_score=round(inventory_health_score, 2),
        estimated_turnover_days=int(turnover_days) if turnover_days < 999 else None,
        demand_elasticity=elasticity,
        demand_elasticity_confidence=0.7 if sales_data.get("promotion_history") else 0.45,
        product_lifecycle_stage=str(product.get("product_lifecycle_stage") or "maturity"),
        lifecycle_evidence="基于数据库销量窗口和新品标记推断",
        has_anomalies=False,
        anomaly_list=[],
        recommended_action=action,
        recommended_discount_range=(min_rate, max_rate),
        recommendation_confidence=round(confidence, 4),
        recommendation_reasons=reasons,
        analysis_details={
            "avg_sales_7d": metrics["avg_sales_7d"],
            "avg_sales_30d": metrics["avg_sales_30d"],
            "avg_sales_90d": metrics["avg_sales_90d"],
            "tool_trace": payload["tool_trace"],
            "data_source": payload["database_context"].get("source", "request_payload"),
        },
        data_quality_score=float(metrics["data_quality_score"]),
        limitations=limitations,
        thinking_process=thinking,
        reasoning=reasoning,
        decision_summary=f"数据分析建议：{action}，建议折扣区间 {min_rate:.2f}-{max_rate:.2f}。",
        confidence=round(confidence, 4),
    )


def run_market_intel_agent(request: AnalysisRequest) -> MarketIntelResult:
    market_payload = _build_market_payload(request)
    market_metrics = MarketSnapshotTool().calculate(market_payload)

    competitors: List[CompetitorInfo] = [
        CompetitorInfo(
            competitor_id=str(item.get("competitor_id") or f"COMP_{index}"),
            product_name=str(item.get("product_name") or item.get("title") or ""),
            current_price=float(item.get("current_price") or 0.0),
            original_price=float(item["original_price"]) if item.get("original_price") is not None else None,
            sales_volume=int(item.get("sales_volume") or 0),
            rating=float(item.get("rating") or 0.0) if item.get("rating") is not None else None,
            review_count=int(item.get("review_count") or 0) if item.get("review_count") is not None else None,
            shop_type=str(item.get("shop_type") or ""),
            is_self_operated=bool(item.get("is_self_operated")),
            promotion_tags=list(item.get("promotion_tags") or []),
        )
        for index, item in enumerate(market_payload.get("competitors", []), start=1)
    ]

    prices = [item.current_price for item in competitors if item.current_price > 0]
    current_price = float(request.product.current_price)
    competition_score = _clamp(
        len(competitors) / 12.0 + market_metrics["promotion_competitor_count"] / max(1, len(competitors)) * 0.35,
        0.0,
        1.0,
    )
    if competition_score >= 0.7:
        competition_level = "fierce"
    elif competition_score >= 0.35:
        competition_level = "moderate"
    else:
        competition_level = "low"

    avg_price = float(market_metrics["avg_competitor_price"]) if market_metrics["avg_competitor_price"] is not None else None
    min_price = float(market_metrics["min_competitor_price"]) if market_metrics["min_competitor_price"] is not None else None
    max_price = float(market_metrics["max_competitor_price"]) if market_metrics["max_competitor_price"] is not None else None
    if prices:
        lower_count = sum(1 for value in prices if value < current_price)
        price_percentile = lower_count / len(prices)
        price_gap = (current_price - avg_price) / max(avg_price or 1.0, 1e-6)
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

    live_market_available = bool(market_metrics["market_data_reliable"])
    suggestion = "maintain"
    reasons: List[str] = []
    limitations = [str(item) for item in list(market_payload.get("warnings", [])) if item]

    if not live_market_available:
        if market_payload.get("blocked") and not any("风控" in item for item in limitations):
            limitations.append("市场数据源不可用，未能生成可用竞品数据。")
        if not limitations:
            limitations.append("未生成可解析的竞品市场样本。")
        failure_reason = "；".join(limitations[:2])
        reasons.append(f"无法生成市场情报样本：{failure_reason}。")
        confidence = 0.32
    else:
        if price_position == "premium" and competition_level == "fierce":
            suggestion = "discount"
            reasons.append("当前定价高于竞品均值且市场竞争激烈，存在转化流失风险。")
        elif price_position == "budget" and competition_level == "low":
            suggestion = "premium"
            reasons.append("当前价格低于竞品均值且竞争不强，可尝试回收部分利润。")
        else:
            reasons.append("竞品价格带与当前价格接近，建议先维持价格。")
        confidence = _clamp(0.48 + competition_score * 0.25, 0.42, 0.82)

    thinking = "先生成模拟真实竞品样本，再用市场分析工具计算竞争强度和价格带。"
    reasoning = (
        f"竞品数量 {len(competitors)}，竞品均价 {avg_price if avg_price is not None else '未知'}，"
        f"当前价格分位 {price_percentile:.2f}，实时市场可用={live_market_available}。"
    )

    return MarketIntelResult(
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
        thinking_process=thinking,
        reasoning=reasoning,
        decision_summary=f"市场情报建议：{suggestion}。",
        confidence=round(confidence, 4),
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
    constraint_conflict = bool(calc["constraint_conflict"])
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
        f"最低安全价 {required_min_price:.2f}",
        f"当前毛利率 {current_margin:.1%}",
        f"综合风险分 {risk_score:.2f}",
    ]
    if refund_rate > 0.05:
        warnings.append(f"退款率偏高（{refund_rate:.1%}）。")
    if complaint_rate > 0.01:
        warnings.append(f"投诉率偏高（{complaint_rate:.1%}）。")
    if stock_age_days >= 90:
        warnings.append(f"库存库龄偏高（{stock_age_days} 天）。")
    if constraint_conflict:
        warnings.append("前端约束存在冲突，无法同时满足最低利润与最高售价。")

    recommendation = "maintain"
    veto_reason: Optional[str] = None
    allow_promotion = False
    if constraint_conflict:
        recommendation = "maintain"
        veto_reason = "约束冲突，需先调整前端输入条件。"
    elif floor_breach:
        recommendation = "increase"
        veto_reason = f"当前价格 {current_price:.2f} 低于最低安全价 {required_min_price:.2f}。"
    elif ceiling_breach:
        recommendation = "discount"
        allow_promotion = True
        reasons.append(f"当前价格高于最高售价约束 {float(price_ceiling):.2f}。")
    else:
        allow_promotion = risk_level != "high" and max_safe_discount < 1.0
        recommendation = "discount" if allow_promotion else "maintain"
        if not allow_promotion:
            veto_reason = "在当前利润和风险边界下，不建议主动降价。"

    discounted_price = max(current_price * max_safe_discount, 0.01)
    profit_margin_after_discount = (
        (discounted_price - float(calc["total_cost"])) / discounted_price if discounted_price > 0 else 0.0
    )

    thinking = "先从数据库读取成本和经营上下文，再用风险计算工具校验利润底线、价格约束和经营风险。"
    reasoning = (
        f"总成本 {float(calc['total_cost']):.2f}，最低安全价 {required_min_price:.2f}，"
        f"价格上限 {price_ceiling if price_ceiling is not None else '无'}，综合风险 {risk_level}。"
    )

    return RiskControlResult(
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
        discount_conditions=[] if allow_promotion else ["未满足主动降价条件"],
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
            "total_cost": float(calc["total_cost"]),
        },
        compliance_check=current_price_compliant,
        veto_reason=veto_reason,
        thinking_process=thinking,
        reasoning=reasoning,
        decision_summary=f"风险控制建议：{recommendation}。",
        confidence=round(_clamp(1.0 - risk_score / 120.0, 0.2, 0.92), 4),
    )


def run_manager_coordinator_agent(
    request: AnalysisRequest,
    data_result: DataAnalysisResult,
    market_result: MarketIntelResult,
    risk_result: RiskControlResult,
) -> FinalDecision:
    conflicts: List[ConflictResolution] = []
    market_live_available = bool(market_result.analysis_details.get("live_market_available"))
    price_ceiling = request.risk_data.price_ceiling
    required_min_price = risk_result.required_min_price
    current_price = max(float(request.product.current_price), 0.01)
    strategy_goal = (request.strategy_goal or "MAX_PROFIT").upper()

    if data_result.recommended_action in {"discount", "clearance"} and not risk_result.allow_promotion:
        conflicts.append(
            ConflictResolution(
                agent1="数据分析",
                agent2="风险控制",
                conflict="数据分析认为可以降价，但风险控制不允许。",
                resolution="以风险控制的硬约束优先。",
                priority="risk_control",
            )
        )
    if market_result.market_suggestion in {"discount", "penetrate", "price_war"} and not risk_result.allow_promotion:
        conflicts.append(
            ConflictResolution(
                agent1="市场情报",
                agent2="风险控制",
                conflict="市场情报认为可以降价，但风险控制不允许。",
                resolution="以风险控制的硬约束优先。",
                priority="risk_control",
            )
        )

    decision = "maintain"
    suggested_price = current_price
    discount_rate = 1.0
    key_factors: List[str] = []
    warnings = list(risk_result.warnings[:3])

    if risk_result.calculation_details.get("constraint_conflict"):
        key_factors = ["约束冲突", "人工复核"]
        warnings.append("前端约束存在冲突，系统已拒绝给出激进价格动作。")
        core_reasons = "无法同时满足前端约束中的最低利润和最高售价，请先修正条件。"
    elif risk_result.calculation_details.get("floor_breach"):
        decision = "increase"
        suggested_price = required_min_price
        discount_rate = round(suggested_price / current_price, 4)
        key_factors = ["利润底线", "价格修复"]
        core_reasons = f"当前售价低于最低安全价 {required_min_price:.2f}，必须先修复利润底线。"
    elif risk_result.calculation_details.get("ceiling_breach") and price_ceiling is not None:
        decision = "discount"
        suggested_price = float(price_ceiling)
        discount_rate = round(suggested_price / current_price, 4)
        key_factors = ["价格上限", "约束满足"]
        core_reasons = f"当前售价高于前端约束上限 {float(price_ceiling):.2f}，需下调以满足约束。"
    elif not risk_result.allow_promotion:
        key_factors = ["风险控制", "利润安全"]
        core_reasons = risk_result.veto_reason or "当前风险与利润边界不支持主动调价。"
        if strategy_goal in {"CLEARANCE", "MARKET_SHARE"}:
            warnings.append("策略目标要求主动调价，但被风险约束阻断，已退化为维持原价。")
    elif settings.market_live_required_for_discount and not market_live_available:
        key_factors = ["市场数据缺失", "保守模式"]
        market_failure_reasons = [str(item) for item in market_result.limitations if item]
        failure_text = "；".join(market_failure_reasons[:2]) if market_failure_reasons else "未知原因"
        core_reasons = f"无法获取实时竞品数据（{failure_text}）。为避免错误降价，系统维持原价。"
        warnings.append(f"市场情报抓取失败：{failure_text}。")
    else:
        candidate_rate = 1.0
        if strategy_goal == "CLEARANCE":
            key_factors = ["清仓目标", "库存去化", "风险边界"]
            candidate_rate = min(data_result.recommended_discount_range[0], 0.96)
            if data_result.inventory_status in {"severe_overstock", "overstock"}:
                candidate_rate = min(candidate_rate, 0.94)
        elif strategy_goal == "MARKET_SHARE":
            key_factors = ["市场份额", "竞品压力", "转化效率"]
            if market_result.market_suggestion in {"discount", "penetrate", "price_war"}:
                candidate_rate = min(data_result.recommended_discount_range[0], 0.97)
            elif market_result.competition_level == "fierce":
                candidate_rate = 0.98
            else:
                candidate_rate = 1.0
        elif strategy_goal == "MAX_PROFIT":
            key_factors = ["利润目标", "单位毛利", "风险边界"]
            if market_result.market_suggestion == "premium" and price_ceiling is None:
                candidate_rate = 1.03
            elif data_result.recommended_action in {"discount", "clearance"} and data_result.inventory_status in {
                "severe_overstock",
                "overstock",
            }:
                candidate_rate = min(data_result.recommended_discount_range[0], 0.98)
            else:
                candidate_rate = 1.0
        else:
            key_factors = ["信号稳定", "约束优先"]
            candidate_rate = 1.0

        if candidate_rate < 1.0:
            decision = "discount"
            discount_rate = max(candidate_rate, risk_result.max_safe_discount)
            suggested_price = round(current_price * discount_rate, 2)
        elif candidate_rate > 1.0:
            decision = "increase"
            discount_rate = candidate_rate
            suggested_price = round(current_price * discount_rate, 2)

        core_reasons = (
            f"策略目标={strategy_goal}；数据建议={data_result.recommended_action}，"
            f"市场建议={market_result.market_suggestion}，风险建议={risk_result.recommendation}。"
        )

    if price_ceiling is not None:
        suggested_price = min(suggested_price, float(price_ceiling))
    suggested_price = max(suggested_price, required_min_price if decision == "increase" else required_min_price if decision == "discount" and suggested_price < required_min_price and price_ceiling is None else suggested_price)

    if decision == "discount" and suggested_price >= current_price - 0.01:
        decision = "maintain"
        suggested_price = current_price
        discount_rate = 1.0
    if decision == "increase" and suggested_price <= current_price + 0.01:
        decision = "maintain"
        suggested_price = current_price
        discount_rate = 1.0

    if decision == "discount":
        price_cut = max(0.0, 1.0 - discount_rate)
        sales_lift = round(1.0 + price_cut * abs(data_result.demand_elasticity or -0.9), 3)
        new_margin = risk_result.profit_margin_after_discount or risk_result.current_profit_margin
        profit_change = round(new_margin * sales_lift - risk_result.current_profit_margin, 4)
        market_share_change = round(price_cut * 0.18, 4)
    elif decision == "increase":
        sales_lift = 0.965
        profit_change = round((discount_rate - 1.0) * 0.75, 4)
        market_share_change = -0.02
    else:
        sales_lift = 1.0
        profit_change = 0.0
        market_share_change = 0.0

    # 策略目标强约束：先满足约束，再校验目标偏离。
    if strategy_goal == "MAX_PROFIT" and decision == "discount" and profit_change <= 0:
        decision = "maintain"
        suggested_price = current_price
        discount_rate = 1.0
        sales_lift = 1.0
        market_share_change = 0.0
        profit_change = 0.0
        warnings.append("MAX_PROFIT 目标下，降价未改善利润，已自动回退为维持原价。")

    if strategy_goal == "CLEARANCE" and decision == "increase":
        decision = "maintain"
        suggested_price = current_price
        discount_rate = 1.0
        sales_lift = 1.0
        market_share_change = 0.0
        profit_change = 0.0
        warnings.append("CLEARANCE 目标不允许主动涨价，已自动回退为维持原价。")

    confidence = _clamp(
        (data_result.recommendation_confidence + market_result.suggestion_confidence + risk_result.confidence) / 3,
        0.28,
        0.88,
    )
    if not market_live_available:
        confidence = min(confidence, 0.56)
    if risk_result.calculation_details.get("constraint_conflict"):
        confidence = min(confidence, 0.3)

    execution_plan = [
        ExecutionPlan(step=1, action=f"将商品价格更新为 {suggested_price:.2f}", timing="立即", responsible="运营"),
        ExecutionPlan(step=2, action="观察 24 小时内转化率、毛利率和退款率变化", timing="24 小时", responsible="分析师"),
    ]

    if decision == "discount" and not market_live_available:
        execution_plan[0].action = f"先小流量测试价格 {suggested_price:.2f}，再决定是否全量"

    thinking = "决策经理汇总三位 agent 的结论，并逐条校验前端约束、利润底线和实时市场数据可用性。"
    reasoning = core_reasons
    conflict_summary = "; ".join(item.resolution for item in conflicts)
    report_text = (
        f"思考：{thinking}\n"
        f"推理：{reasoning}\n"
        f"决策：{decision}，建议价 {suggested_price:.2f}\n"
        f"冲突：{conflict_summary or '无'}"
    )

    return FinalDecision(
        decision=decision,
        discount_rate=round(discount_rate, 4),
        suggested_price=round(suggested_price, 2),
        confidence=round(confidence, 4),
        expected_outcomes=ExpectedOutcomes(
            sales_lift=sales_lift,
            profit_change=profit_change,
            market_share_change=market_share_change,
        ),
        core_reasons=core_reasons,
        key_factors=key_factors,
        conflicts_detected=conflicts,
        risk_warning=risk_result.veto_reason or ("无阻断性风险" if risk_result.allow_promotion else "风险控制要求保守执行"),
        contingency_plan="若 24 小时内转化率下滑超过 8% 或退款率异常抬升，应立即回滚价格并重新评估。",
        execution_plan=execution_plan,
        report_text=report_text,
        agent_summaries=[
            AgentSummary(agent_name="数据分析", summary=data_result.decision_summary, key_points=data_result.recommendation_reasons[:3]),
            AgentSummary(agent_name="市场情报", summary=market_result.decision_summary, key_points=market_result.suggestion_reasons[:3]),
            AgentSummary(agent_name="风险控制", summary=risk_result.decision_summary, key_points=risk_result.recommendation_reasons[:3]),
        ],
        decision_framework="数据库取数 + 模拟竞品市场数据 + 风控约束 + 经理协同",
        alternative_options=[
            {"option": "维持原价", "discount_rate": 1.0},
            {"option": "边界内最小降价", "discount_rate": risk_result.max_safe_discount},
        ],
        thinking_process=thinking,
        reasoning=reasoning,
        conflict_summary=conflict_summary,
        warnings=warnings,
        agent_summaries_structured={
            "dataAnalysis": {
                "salesTrend": data_result.sales_trend,
                "inventoryStatus": data_result.inventory_status,
                "suggestedDiscountRange": data_result.recommended_discount_range,
            },
            "marketIntel": {
                "competitionLevel": market_result.competition_level,
                "pricePosition": market_result.price_position,
                "liveMarketAvailable": market_live_available,
            },
            "riskControl": {
                "riskLevel": risk_result.risk_level,
                "requiredMinPrice": risk_result.required_min_price,
                "allowPromotion": risk_result.allow_promotion,
            },
        },
    )
