"""Map validated Agent outputs to frontend Agent Card payloads."""

from __future__ import annotations

from typing import Any

from app.crew.protocols import CrewRunPayload
from app.agent_outputs.normalizer import first_present, normalize_optional_text, normalize_selected_agent
from app.utils.math_utils import money
from app.utils.text_utils import MANUAL_REVIEW_STRATEGY, to_risk_level_cn, to_strategy_goal_cn


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _safe_float_in_range(val: Any, minimum: float, maximum: float) -> float | None:
    try:
        parsed = float(val)
    except (TypeError, ValueError):
        return None
    if parsed < minimum or parsed > maximum:
        return None
    return parsed


def _safe_optional_float(val: Any) -> float | None:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _safe_rate_change(new_value: Any, old_value: Any) -> float | None:
    try:
        new_numeric = float(new_value)
        old_numeric = float(old_value)
    except (TypeError, ValueError):
        return None
    if old_numeric <= 0:
        return None
    return round((new_numeric - old_numeric) / old_numeric, 4)


def _safe_money_delta(new_value: Any, old_value: Any) -> float | None:
    try:
        return round(float(new_value) - float(old_value), 2)
    except (TypeError, ValueError):
        return None


def _normalize_optional_list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []
    return [item for item in value if item is not None]


def build_failed_card(summary: str) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    concise = str(summary or "").strip() or "CrewAI 任务执行失败"
    return (
        concise,
        [{"label": "错误摘要", "value": concise}],
        {"error": True, "message": concise},
    )


def build_data_card(payload: CrewRunPayload, parsed: dict[str, Any]) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    thinking = parsed.get("thinking", "基于商品经营数据评估价格弹性与利润-销量关系，给出数据驱动的建议价格区间。")
    evidence = [
        {"label": "策略目标", "value": to_strategy_goal_cn(payload.strategy_goal)},
        {"label": "基线销量(月)", "value": int(payload.baseline_sales)},
        {"label": "基线利润(月)", "value": float(money(payload.baseline_profit))},
        {"label": "当前售价", "value": float(money(payload.product.current_price))},
        {"label": "成本价", "value": float(money(payload.product.cost_price))},
    ]

    suggested_price = _safe_float(parsed.get("suggestedPrice"))
    min_price = _safe_float(parsed.get("suggestedMinPrice"))
    max_price = _safe_float(parsed.get("suggestedMaxPrice"))
    expected_sales = _safe_int(parsed.get("expectedSales"))
    expected_profit = _safe_float(parsed.get("expectedProfit"))
    price_change_rate = _safe_rate_change(suggested_price, payload.product.current_price)
    profit_growth = _safe_money_delta(expected_profit, payload.baseline_profit)

    suggestion = {
        "priceRange": {"min": min_price, "max": max_price},
        "recommendedPrice": suggested_price,
        "expectedSales": expected_sales,
        "expectedProfit": expected_profit,
        "priceChangeRate": price_change_rate,
        "profitGrowth": profit_growth,
        "expectedProfitRate": round(expected_profit / max(suggested_price * max(expected_sales, 1), 0.01), 4),
        "merchantPainPoint": "判断调价后销量和利润是否划算，避免只看价格不看收益",
        "merchantAction": "优先查看利润变化，再结合市场与风控确认是否采用",
        "summary": parsed.get("summary", "数据分析完成"),
    }
    return thinking, evidence, suggestion


def build_market_card(parsed: dict[str, Any]) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    thinking = parsed.get("thinking", "基于竞品价格数据分析市场价格带和竞争态势，给出市场可接受的建议价格。")

    sample_count = _safe_int(parsed.get("competitorSamples"))
    raw_count = _safe_int(parsed.get("rawItemCount", sample_count))
    filtered_count = _safe_int(parsed.get("filteredItemCount", sample_count))
    market_floor = _safe_float(parsed.get("marketFloor"))
    market_median = _safe_float(parsed.get("marketMedian"))
    market_ceiling = _safe_float(parsed.get("marketCeiling"))
    market_average = _safe_float(parsed.get("marketAverage"))
    valid_count = _safe_int(parsed.get("usedCompetitorCount", parsed.get("validCompetitorCount", sample_count)))
    source = str(parsed.get("source", "UNKNOWN"))
    source_status = str(parsed.get("sourceStatus", "UNKNOWN"))
    data_quality = str(parsed.get("dataQuality", "LOW"))
    quality_reasons = parsed.get("qualityReasons")
    pricing_position = normalize_optional_text(parsed.get("pricingPosition")) or ""
    evidence_summary = normalize_optional_text(parsed.get("evidenceSummary")) or ""

    risk_notes = normalize_optional_text(parsed.get("riskNotes"))
    degraded = source_status.upper() != "OK" or data_quality.upper() == "LOW" or valid_count < 3
    if not risk_notes and degraded:
        risk_notes = "本次竞品数据不足，仅供参考"
    if source_status.upper() != "OK":
        merchant_action = "先补充竞品数据或手动复核，不建议按市场价大幅调价"
    elif data_quality.upper() == "LOW" or valid_count < 3:
        merchant_action = "竞品样本偏少，建议小幅试探并保留人工复核"
    else:
        merchant_action = "竞品数据可信，可结合价格带判断是否跟随、卡位或避开低价竞争"

    evidence = [
        {"label": "有效样本数", "value": valid_count},
        {"label": "市场最低价", "value": market_floor},
        {"label": "市场中位价", "value": market_median},
        {"label": "市场最高价", "value": market_ceiling},
        {"label": "市场均价", "value": market_average},
        {"label": "竞品来源", "value": source},
        {"label": "竞品状态", "value": source_status},
        {"label": "数据质量", "value": data_quality},
    ]

    brand_breakdown = parsed.get("brandBreakdown") or []
    if isinstance(brand_breakdown, list) and brand_breakdown:
        evidence.append({"label": "品牌价格带", "value": brand_breakdown[:5]})

    promotion_density = parsed.get("promotionDensity") or {}
    if isinstance(promotion_density, dict) and promotion_density:
        evidence.append({"label": "促销密度", "value": promotion_density})

    if quality_reasons:
        evidence.append({"label": "质量原因", "value": quality_reasons})
    if evidence_summary:
        evidence.append({"label": "证据摘要", "value": evidence_summary})

    suggestion = {
        "priceRange": {"min": market_floor, "max": market_ceiling},
        "recommendedPrice": float(parsed.get("suggestedPrice", 0)),
        "marketScore": round(float(parsed.get("confidence", 0.5)) * 100, 2),
        "source": source,
        "sourceStatus": source_status,
        "dataQuality": data_quality,
        "pricingPosition": None,
        "usedCompetitorCount": valid_count,
        "riskNotes": risk_notes,
        "evidenceSummary": evidence_summary or None,
        "salesWeightedAverage": None,
        "merchantPainPoint": "判断竞品价格能否支撑调价，避免卖贵丢单或卖便宜少赚",
        "merchantAction": merchant_action,
        "summary": parsed.get("summary", "市场情报分析完成"),
    }
    return thinking, evidence, suggestion


def build_risk_card(payload: CrewRunPayload, parsed: dict[str, Any]) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    thinking = parsed.get("thinking", "对候选价格执行成本底线与利润约束校验，判断是否允许自动执行。")

    is_pass = bool(parsed.get("isPass", False))
    safe_floor = _safe_float(parsed.get("safeFloorPrice"))
    suggested = _safe_float(parsed.get("suggestedPrice"))
    risk_level = str(parsed.get("riskLevel", "HIGH"))

    evidence = [
        {"label": "风控建议价", "value": suggested},
        {"label": "安全底价", "value": safe_floor},
        {"label": "基线利润(月)", "value": float(money(payload.baseline_profit))},
        {"label": "硬约束通过", "value": is_pass},
    ]

    suggestion = {
        "recommendedPrice": suggested,
        "safeFloorPrice": safe_floor,
        "pass": is_pass,
        "riskLevel": to_risk_level_cn(risk_level),
        "needManualReview": bool(parsed.get("needManualReview", not is_pass)),
        "action": "自动执行" if is_pass else "人工审核",
        "merchantPainPoint": "确认是否会亏损、低毛利或突破商家设置的价格红线",
        "merchantAction": "已满足价格红线，可进入人工审核确认活动节奏" if is_pass else "按安全底价或约束修正后再提交人工审核",
        "summary": parsed.get("summary", "风控评估完成"),
    }
    return thinking, evidence, suggestion


def build_manager_card(
    parsed: dict[str, Any],
    data_parsed: dict[str, Any],
    market_parsed: dict[str, Any],
    risk_parsed: dict[str, Any],
) -> tuple[str, list[dict[str, Any]], dict[str, Any], str]:
    thinking = parsed.get("thinking", "综合前三个Agent的意见，输出最终可执行的定价决策。")

    evidence = [
        {"label": "数据分析建议价", "value": _safe_float(data_parsed.get("suggestedPrice"))},
        {"label": "市场情报建议价", "value": _safe_float(market_parsed.get("suggestedPrice"))},
        {"label": "风险控制建议价", "value": _safe_float(risk_parsed.get("suggestedPrice"))},
        {"label": "风控通过", "value": bool(risk_parsed.get("isPass", False))},
    ]

    disagreement_points = _normalize_optional_list(
        first_present(parsed, "disagreementPoints", "conflicts", "disagreements", "conflictPoints")
    )
    accepted_opinions = _normalize_optional_list(parsed.get("acceptedOpinions"))
    rejected_opinions = _normalize_optional_list(parsed.get("rejectedOpinions"))

    suggestion = {
        "finalPrice": _safe_float(parsed.get("finalPrice")),
        "expectedSales": _safe_int(parsed.get("expectedSales")),
        "expectedProfit": _safe_float(parsed.get("expectedProfit")),
        "profitGrowth": _safe_optional_float(parsed.get("profitGrowth")),
        "strategy": MANUAL_REVIEW_STRATEGY,
        "consensusScore": _safe_float_in_range(parsed.get("consensusScore"), 0.0, 1.0),
        "disagreementSummary": normalize_optional_text(parsed.get("disagreementSummary")),
        "disagreementPoints": disagreement_points,
        "acceptedOpinions": accepted_opinions,
        "rejectedOpinions": rejected_opinions,
        "arbitrationDecision": normalize_optional_text(
            first_present(parsed, "arbitrationDecision", "arbitrationSummary", "decisionSummary")
        ),
        "arbitrationReason": normalize_optional_text(first_present(parsed, "arbitrationReason", "decisionReason")),
        "selectedAgent": normalize_selected_agent(first_present(parsed, "selectedAgent", "selectedOption")),
        "selectedPrice": _safe_optional_float(parsed.get("selectedPrice")),
        "selectedStrategy": normalize_optional_text(parsed.get("selectedStrategy")),
        "merchantPainPoint": "给出商家可落地的最终价格、预期收益和复核动作",
        "merchantAction": "进入人工审核，核对库存、活动节奏后再应用建议价",
        "summary": parsed.get("resultSummary", "综合决策完成"),
    }
    reason_why = str(parsed.get("resultSummary", "综合数据、市场、风控意见给出最终建议价格。"))
    return thinking, evidence, suggestion, reason_why

