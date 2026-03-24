"""本地四智能体定价逻辑。

主链路分为四步：
1. 数据分析智能体读取销量与库存信号
2. 市场情报智能体读取竞品与市场价格信号
3. 风险控制智能体计算利润底线与约束边界
4. 决策经理综合前三者方案，产出最终建议
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
    """把数值限制在给定区间内，避免评分或价格越界。"""
    return max(low, min(high, value))


def _safe_mean(values: Sequence[float | int]) -> float:
    """在过滤空值和异常类型后计算均值，供销量与趋势计算复用。"""
    numeric = [float(v) for v in values if isinstance(v, (int, float))]
    if not numeric:
        return 0.0
    return float(mean(numeric))


def _extract_product_id(request: AnalysisRequest) -> Optional[int]:
    """从请求对象中提取商品 ID，方便后续按需走数据库工具链。"""
    try:
        return int(request.product.product_id)
    except (TypeError, ValueError):
        return None


def _load_data_agent_payload(request: AnalysisRequest) -> Dict[str, Any]:
    """为数据分析智能体准备输入。

    优先使用数据库上下文工具读取真实经营数据；如果当前场景不走数据库，
    就退回到请求体里携带的商品与销量数据。
    """
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
    """为风控智能体准备输入，并把前端约束合并到风险上下文里。"""
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
    """为市场情报智能体准备竞品数据。

    如果请求已经提供竞品，就直接使用；否则调用抓取工具补足一份市场样本。
    在异步环境里会切到线程池，避免阻塞事件循环。
    """
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
    """根据历史促销前后销量变化估算价格弹性。"""
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
    """估算当前价格下的月销量基线，供利润变化计算使用。"""
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
    """根据成本、最低利润率和显式价格下限，算出请求层面的最低可卖价。"""
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
    """把候选价格压到约束区间内，统一处理价格上限和最低安全价。"""
    normalized = max(float(price), 0.01)
    ceiling = request.risk_data.price_ceiling
    if ceiling is not None:
        normalized = min(normalized, float(ceiling))

    floor = float(required_min_price) if required_min_price is not None else _required_min_price_from_request(request)
    if ceiling is None or float(ceiling) >= floor - 0.01:
        normalized = max(normalized, floor)
    return round(normalized, 2)


def _estimate_sales_lift(current_price: float, suggested_price: float, elasticity: Optional[float]) -> float:
    """根据价格弹性估算调价后的销量变化倍数。"""
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
    """估算调价后相对当前价格的月利润增减额。"""
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
    """把建议价转换成业务动作：提价、降价或维持原价。"""
    if suggested_price > current_price + 0.01:
        return "increase"
    if suggested_price < current_price - 0.01:
        return "discount"
    return "maintain"


def _to_cn_action(action: str) -> str:
    """把内部动作码翻译成前端可读的中文动作描述。"""
    mapping = {
        "maintain": "维持原价",
        "discount": "小幅降价",
        "increase": "适度提价",
        "clearance": "清仓促销",
        "premium": "上探价格带",
        "penetrate": "渗透定价",
        "price_war": "竞争性降价",
    }
    return mapping.get(str(action or "").lower(), str(action or "维持原价"))


def _to_cn_agent_name(agent_name: str) -> str:
    """把内部智能体名称翻译成中文角色名。"""
    mapping = {
        "data": "数据分析",
        "market": "市场情报",
        "risk": "风险控制",
        "manager_midpoint": "经理协调",
        "manager_revision": "经理复核",
        "manager": "决策经理",
    }
    return mapping.get(str(agent_name or "").lower(), str(agent_name or "未知"))


def _to_cn_risk_level(level: str) -> str:
    mapping = {"high": "高风险", "medium": "中风险", "low": "低风险"}
    return mapping.get(str(level or "").lower(), "中风险")


def _describe_discount_range(min_rate: float, max_rate: float) -> str:
    """把折扣系数区间转换成自然语言描述。"""
    min_rate = float(min_rate)
    max_rate = float(max_rate)
    if abs(min_rate - 1.0) < 1e-6 and abs(max_rate - 1.0) < 1e-6:
        return "当前建议维持原价，不做折扣。"
    if min_rate <= 1.0 and max_rate <= 1.0:
        min_drop = max(0.0, 1.0 - max_rate)
        max_drop = max(0.0, 1.0 - min_rate)
        return f"建议折扣系数区间 {min_rate:.2f}-{max_rate:.2f}（约降价 {min_drop:.0%}-{max_drop:.0%}）。"
    return f"建议价格调整系数区间 {min_rate:.2f}-{max_rate:.2f}。"


def _goal_code(request: AnalysisRequest) -> str:
    """统一读取策略目标，避免各个智能体分别处理大小写和空值。"""
    return str(request.strategy_goal or "MAX_PROFIT").upper()


def _forced_decision_by_constraints(
    request: AnalysisRequest,
    required_min_price: Optional[float] = None,
) -> Optional[tuple[str, float]]:
    """先判断是否存在必须立即执行的硬约束动作。

    例如当前价格已经低于最低安全价，或者高于价格上限，这类情况不再交给
    智能体自由讨论，而是直接返回强制动作和对应价格。
    """
    current_price = max(float(request.product.current_price), 0.01)
    price_ceiling = request.risk_data.price_ceiling
    floor = float(required_min_price) if required_min_price is not None else _required_min_price_from_request(request)

    if price_ceiling is not None and float(price_ceiling) < floor - 0.01:
        return None
    if current_price + 1e-6 < floor:
        return "increase", round(floor, 2)
    if price_ceiling is not None and current_price > float(price_ceiling) + 1e-6:
        return "discount", round(float(price_ceiling), 2)
    return None


def _market_suggestion_to_decision(suggestion: str) -> str:
    """把市场智能体的建议类型归一成统一决策动作。"""
    normalized = str(suggestion or "maintain").lower()
    if normalized in {"discount", "penetrate", "price_war"}:
        return "discount"
    if normalized == "premium":
        return "increase"
    return "maintain"


def _decision_to_market_suggestion(decision: str) -> str:
    """把统一决策动作翻回市场智能体使用的建议标签。"""
    normalized = str(decision or "maintain").lower()
    if normalized == "discount":
        return "discount"
    if normalized == "increase":
        return "premium"
    return "maintain"


def _evaluate_request_candidate(
    request: AnalysisRequest,
    candidate_price: float,
    elasticity: Optional[float],
    required_min_price: Optional[float] = None,
) -> Dict[str, float | str]:
    """评估单个候选价格的业务效果。

    这里统一输出动作方向、建议价、折扣系数、销量变化和利润变化，
    让三类智能体与经理都能使用同一套评分口径。
    """
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
    allowed_decisions: Optional[Sequence[str]] = None,
) -> Dict[str, float | str]:
    """从一组候选调价系数中挑选最优方案。

    先把所有候选统一换算成完整评估结果，再按允许方向过滤，
    最后优先选择“满足目标方向且利润更优”的方案。
    """
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

    if allowed_decisions:
        allowed = {str(item).lower() for item in allowed_decisions}
        filtered = [item for item in candidates if str(item["decision"]).lower() in allowed]
        if filtered:
            candidates = filtered
        else:
            maintain = next((item for item in by_price.values() if str(item["decision"]).lower() == "maintain"), None)
            if maintain is not None:
                return maintain
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
    """把数据分析结论转换成一个可执行的建议价格。"""
    current_price = max(float(request.product.current_price), 0.01)
    action = str(result.recommended_action or "maintain").lower()
    inventory_status = str(result.inventory_status or "normal").lower()
    sales_trend = str(result.sales_trend or "stable").lower()

    forced = _forced_decision_by_constraints(request)
    if forced is not None:
        return float(forced[1])
    if action == "maintain":
        return round(current_price, 2)

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
        allowed_decisions=[preferred_decision],
    )
    return float(best["suggested_price"])


def _derive_market_agent_suggested_price(request: AnalysisRequest, result: MarketIntelResult) -> float:
    """把市场判断转成具体价格，确保方向和文案结论一致。"""
    current_price = max(float(request.product.current_price), 0.01)
    market_suggestion = str(result.market_suggestion or "maintain").lower()
    competition_level = str(result.competition_level or "moderate").lower()
    price_position = str(result.price_position or "mid-range").lower()
    avg_price = float(result.avg_competitor_price) if result.avg_competitor_price is not None else None

    forced = _forced_decision_by_constraints(request)
    if forced is not None:
        return float(forced[1])
    target_decision = _market_suggestion_to_decision(market_suggestion)
    if target_decision == "maintain":
        return round(current_price, 2)

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
        allowed_decisions=[target_decision],
    )
    return float(best["suggested_price"])


def _derive_risk_agent_suggested_price(request: AnalysisRequest, result: RiskControlResult) -> float:
    """在风控边界内生成最终可落地的风控建议价格。"""
    current_price = max(float(request.product.current_price), 0.01)
    price_ceiling = request.risk_data.price_ceiling

    if result.calculation_details.get("constraint_conflict"):
        return round(current_price, 2)
    forced = _forced_decision_by_constraints(request, required_min_price=float(result.required_min_price))
    if forced is not None:
        return float(forced[1])

    target_decision = str(result.recommendation or "maintain").lower()
    if target_decision == "maintain":
        return round(current_price, 2)

    candidate_rates: List[float] = [1.0, 1.01, 1.02, 1.03]
    if str(result.risk_level or "").lower() == "low":
        candidate_rates.extend([1.04, 1.05])

    if result.allow_promotion:
        candidate_rates.extend([0.99, 0.98, float(result.max_safe_discount or 1.0)])
        preferred_decision = "discount" if target_decision == "discount" else "increase"
    else:
        preferred_decision = "increase"

    best = _pick_best_candidate(
        request=request,
        candidate_rates=candidate_rates,
        elasticity=-0.8,
        preferred_decision=preferred_decision,
        required_min_price=float(result.required_min_price),
        allowed_decisions=[target_decision],
    )
    chosen_price = float(best["suggested_price"])
    if price_ceiling is not None:
        chosen_price = min(chosen_price, float(price_ceiling))
    if price_ceiling is None or float(price_ceiling) >= float(result.required_min_price) - 0.01:
        chosen_price = max(chosen_price, float(result.required_min_price))
    return round(chosen_price, 2)


def run_data_analysis_agent(request: AnalysisRequest) -> DataAnalysisResult:
    """运行数据分析智能体。

    这一层只关心经营数据本身：销量趋势、库存周转、库存平衡度，
    然后据此给出数据视角下的动作方向和建议价格。
    """
    payload = _load_data_agent_payload(request)
    metrics = SalesMetricsTool().calculate(payload)
    product = payload["product"]
    sales_data = payload["sales_data"]
    strategy_goal = _goal_code(request)

    # 先把销量趋势和库存周转类指标统一取出，后面所有判断都基于这一组底层信号。
    trend_score = float(metrics.get("trend_score") or 0.0)
    turnover_days_value = float(metrics.get("turnover_days") or 999.0)
    stock_age_days = int(product.get("stock_age_days") or 0)

    if trend_score >= 0.18:
        sales_trend = "rising"
    elif trend_score <= -0.18:
        sales_trend = "declining"
    else:
        sales_trend = "stable"

    # 库存分数看的是“平衡度”，不是单纯看是否积压。
    # 也就是说，库存过多和库存过紧都会扣分。
    inventory_health_score = 100.0
    inventory_health_score -= abs(turnover_days_value - 28.0) * 2.2
    inventory_health_score -= max(0, stock_age_days - 45) * 0.28
    inventory_health_score -= max(0.0, 8.0 - turnover_days_value) * 6.5
    inventory_health_score = _clamp(inventory_health_score, 0.0, 100.0)

    # 先根据库存周转速度判断库存位置，再补充平衡度分数作为解释依据。
    if turnover_days_value <= 10:
        inventory_status = "tight"
    elif turnover_days_value >= 75:
        inventory_status = "severe_overstock"
    elif turnover_days_value >= 45 or inventory_health_score < 48:
        inventory_status = "overstock"
    else:
        inventory_status = "normal"

    elasticity = _demand_elasticity(
        promotion_history=sales_data.get("promotion_history", []),
        current_price=float(product.get("current_price") or 0.0),
        category=str(product.get("category") or ""),
    )

    # 根据目标、库存状态和趋势决定动作方向。
    action = "maintain"
    min_rate, max_rate = 1.0, 1.0
    reasons: List[str] = []
    if inventory_status == "severe_overstock" or turnover_days_value >= 75:
        action = "discount"
        min_rate, max_rate = 0.93, 0.96
        reasons.append(f"库存压力较高（周转天数 {turnover_days_value:.1f} 天）。")
    elif inventory_status == "overstock" and sales_trend == "declining":
        action = "discount"
        min_rate, max_rate = 0.95, 0.98
        reasons.append("需求走弱且库存偏高。")
    elif strategy_goal == "CLEARANCE" and inventory_status != "tight":
        action = "discount"
        min_rate, max_rate = 0.97, 0.99
        reasons.append("任务目标为清仓促销，数据面建议先测试小幅降价。")
    elif strategy_goal == "MARKET_SHARE" and inventory_status != "tight":
        action = "discount"
        min_rate, max_rate = 0.98, 0.99
        reasons.append("任务目标为市场份额优先，数据面建议用小幅降价换取转化。")
    elif inventory_status == "tight" and sales_trend == "rising":
        reasons.append("库存周转偏快，存在潜在缺货风险，暂不建议激进降价。")
    else:
        reasons.append("需求与库存总体稳定。")

    # 最终信心由趋势强弱和数据完整度共同决定。
    confidence = _clamp(0.55 + abs(trend_score) * 0.3 + (0.08 if sales_data.get("promotion_history") else 0.0), 0.35, 0.86)
    limitations: List[str] = []
    if payload["tool_trace"][0] != "database_product_context_tool":
        limitations.append("本次数据分析使用请求载荷，未读取数据库上下文。")
    if float(metrics.get("data_quality_score") or 1.0) < 1.0:
        limitations.append("销售历史不完整，结论可信度已下调。")

    base_result = DataAnalysisResult(
        sales_trend=sales_trend,
        sales_trend_score=round(trend_score, 4),
        inventory_status=inventory_status,
        inventory_health_score=round(inventory_health_score, 2),
        estimated_turnover_days=int(turnover_days_value) if turnover_days_value < 999 else None,
        demand_elasticity=elasticity,
        demand_elasticity_confidence=0.7 if sales_data.get("promotion_history") else 0.45,
        product_lifecycle_stage=str(product.get("product_lifecycle_stage") or "maturity"),
        lifecycle_evidence="基于销售窗口和商品上下文推断。",
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
            "current_price": float(product.get("current_price") or 0.0),
            "tool_trace": payload["tool_trace"],
            "data_source": payload["database_context"].get("source", "request_payload"),
        },
        data_quality_score=float(metrics.get("data_quality_score") or 1.0),
        limitations=limitations,
        thinking_process="先汇总近7/30/90天销量、库存与周转等经营数据，再判断趋势和库存压力。",
        reasoning=(
            f"近7日均销为{float(metrics.get('avg_sales_7d') or 0):.2f}件/天，"
            f"近30日均销为{float(metrics.get('avg_sales_30d') or 0):.2f}件/天，"
            f"短期销量变化率（近7日对比近30日）为{trend_score:.1%}，库存周转天数为{turnover_days_value:.1f}天。"
        ),
        decision_summary=f"数据分析建议：{_to_cn_action(action)}，{_describe_discount_range(min_rate, max_rate)}",
        confidence=round(confidence, 4),
    )

    # 先生成基础结论，再统一换算成可执行价格，避免“建议降价却报出涨价”的不一致。
    suggested_price = _derive_data_agent_suggested_price(request, base_result)
    current_price = float(request.product.current_price or 0.0)
    actual_action = _candidate_decision(current_price, suggested_price)
    updated_reasons = list(reasons)
    updated_min_rate, updated_max_rate = min_rate, max_rate
    if actual_action != action:
        if actual_action == "maintain":
            updated_min_rate, updated_max_rate = 1.0, 1.0
            updated_reasons.append("结合当前利润底线与价格约束，本轮数据侧不建议直接调价。")
        elif actual_action == "increase":
            updated_min_rate = round(suggested_price / max(current_price, 0.01), 4)
            updated_max_rate = updated_min_rate
            updated_reasons.append("为满足当前价格约束，数据侧建议先回到安全价格区间。")
        action = actual_action
        base_result = base_result.model_copy(
            update={
                "recommended_action": action,
                "recommended_discount_range": (updated_min_rate, updated_max_rate),
                "recommendation_reasons": updated_reasons,
                "decision_summary": f"数据分析建议：{_to_cn_action(action)}，{_describe_discount_range(updated_min_rate, updated_max_rate)}",
            }
        )
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
    """运行市场情报智能体。

    这一层聚焦外部市场：竞品多少、均价在哪、当前商品位于高价位还是低价位，
    再结合策略目标给出市场视角下的建议价格。
    """
    market_payload = _build_market_payload(request)
    market_metrics = MarketSnapshotTool().calculate(market_payload)
    strategy_goal = _goal_code(request)

    # 先把原始竞品样本转换成结构化对象，方便后面统一做市场统计。
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

    # 价格分位和竞争强度是市场智能体最核心的两个判断依据。
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

    # 先判断市场数据是否可靠，再决定是否可以激进地给出降价或提价建议。
    live_market_available = bool(market_metrics.get("market_data_reliable"))
    suggestion = "maintain"
    reasons: List[str] = []
    limitations = [str(item) for item in list(market_payload.get("warnings", [])) if item]
    if not live_market_available:
        if market_payload.get("blocked"):
            limitations.append("市场抓取受限或不可用。")
        if not limitations:
            limitations.append("当前请求未获得可靠竞品样本。")
        reasons.append("市场数据可靠性不足，避免激进降价。")
        confidence = 0.32
    else:
        if price_position == "premium" and competition_level == "fierce":
            suggestion = "discount"
            reasons.append("当前定价偏高且竞争激烈。")
        elif price_position == "budget" and competition_level == "low":
            suggestion = "premium"
            reasons.append("当前定价偏低且竞争压力较弱。")
        else:
            reasons.append("当前价格带与竞品接近。")

        if strategy_goal == "CLEARANCE" and price_position != "budget":
            suggestion = "discount"
            reasons.append("任务目标为清仓促销，市场侧优先给出可执行降价方案。")
        elif strategy_goal == "MARKET_SHARE" and competition_level in {"moderate", "fierce"}:
            suggestion = "discount"
            reasons.append("任务目标为市场份额优先，竞争环境下优先换取销量。")
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
        thinking_process="先生成竞品样本，再评估价格定位与竞争压力。",
        reasoning=(
            f"竞品数量为{len(competitors)}个，竞品均价为{(f'{avg_price:.2f}元' if avg_price is not None else '未知')}，"
            f"价格分位为{price_percentile:.1%}，"
            f"{'实时竞品数据已获取，可用于本次定价决策。' if live_market_available else '实时竞品数据不足，当前仅作保守参考。'}"
        ),
        decision_summary=f"市场情报建议：{_to_cn_action(suggestion)}。",
        confidence=round(confidence, 4),
    )

    # 先生成基础市场判断，再换算成具体价格，保持“结论”和“报价”一致。
    suggested_price = _derive_market_agent_suggested_price(request, base_result)
    current_price = float(request.product.current_price or 0.0)
    actual_decision = _candidate_decision(current_price, suggested_price)
    aligned_suggestion = _decision_to_market_suggestion(actual_decision)
    updated_reasons = list(reasons)
    if _market_suggestion_to_decision(suggestion) != actual_decision:
        if actual_decision == "maintain":
            updated_reasons.append("结合利润底线与当前约束，本轮市场侧暂不建议直接调价。")
        elif actual_decision == "increase":
            updated_reasons.append("受价格底线约束影响，市场侧本轮不能执行降价方案。")
        base_result = base_result.model_copy(
            update={
                "market_suggestion": aligned_suggestion,
                "suggestion_reasons": updated_reasons,
                "decision_summary": f"市场情报建议：{_to_cn_action(aligned_suggestion)}。",
            }
        )
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
    """运行风险控制智能体。

    风控不负责追求最优销量，而是负责守住利润、价格上下限和经营风险底线，
    因此这里会优先判断是否存在一票否决或强制调价场景。
    """
    payload = _load_risk_agent_payload(request)
    calc = RiskConstraintTool().calculate(payload)
    product = payload["product"]
    risk = payload["risk_data"]
    strategy_goal = _goal_code(request)

    # 先把会影响风控结论的关键边界全部算出来：当前价格、安全价和价格上限。
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

    # 风险分由利润风险、库存风险、售后风险和约束冲突共同组成。
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
        f"最低安全价为 {required_min_price:.2f}元",
        f"当前毛利率为 {current_margin:.1%}",
        f"风险指数为 {risk_score:.2f}分",
    ]
    if refund_rate > 0.05:
        warnings.append(f"退款率偏高（{refund_rate:.1%}）。")
    if complaint_rate > 0.01:
        warnings.append(f"投诉率偏高（{complaint_rate:.1%}）。")
    if stock_age_days >= 90:
        warnings.append(f"库存库龄偏高（{stock_age_days} 天）。")
    if constraint_conflict:
        warnings.append("价格约束与最低安全价冲突。")

    # 先判断是否存在必须强制处理的风险，再判断是否允许为了目标主动降价。
    recommendation = "maintain"
    veto_reason: Optional[str] = None
    allow_promotion = False
    if constraint_conflict:
        recommendation = "maintain"
        veto_reason = "约束冲突，需先修正条件后再自动定价。"
    elif floor_breach:
        recommendation = "increase"
        veto_reason = f"当前价格 {current_price:.2f}元低于最低安全价 {required_min_price:.2f}元。"
    elif ceiling_breach:
        recommendation = "discount"
        allow_promotion = True
    else:
        allow_promotion = risk_level != "high" and max_safe_discount < 1.0
        if strategy_goal in {"CLEARANCE", "MARKET_SHARE"} and allow_promotion:
            recommendation = "discount"
        else:
            recommendation = "maintain"
        if not allow_promotion:
            veto_reason = "当前风险状态不支持主动降价。"

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
        discount_conditions=[] if allow_promotion else ["当前风险约束下不支持主动降价。"],
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
        thinking_process="先计算硬约束边界，再汇总经营风险因子。",
        reasoning=(
            f"总成本为{unit_total_cost:.2f}元，最低安全价为{required_min_price:.2f}元，"
            f"价格上限为{(f'{float(price_ceiling):.2f}元' if price_ceiling is not None else '无')}，风险等级为{_to_cn_risk_level(risk_level)}。"
            f"最低安全价按 max(总成本, 成本/(1-最低利润率), 成本*(1+最低加价率), 价格下限) 计算。"
        ),
        decision_summary=f"风险控制建议：{_to_cn_action(recommendation)}。",
        confidence=round(_clamp(1.0 - risk_score / 120.0, 0.2, 0.92), 4),
    )

    # 基础结论生成后，再换算成风控口径下真正可执行的价格。
    suggested_price = _derive_risk_agent_suggested_price(request, base_result)
    actual_recommendation = _candidate_decision(float(request.product.current_price or 0.0), suggested_price)
    updated_reasons = list(reasons)
    if actual_recommendation != recommendation:
        if actual_recommendation == "maintain":
            updated_reasons.append("按利润底线与风险约束测算，本轮仅维持当前价格更稳妥。")
        elif actual_recommendation == "increase":
            updated_reasons.append("受最低安全价约束影响，需要先回到安全价格区间。")
        base_result = base_result.model_copy(
            update={
                "recommendation": actual_recommendation,
                "recommendation_reasons": updated_reasons,
                "decision_summary": f"风险控制建议：{_to_cn_action(actual_recommendation)}。",
            }
        )
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
    """按经理统一口径复核单个提案价格。"""
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
    """识别三类智能体之间的方向冲突和价差冲突，供经理协调时引用。"""
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
                conflict="存在提价与降价方向冲突。",
                resolution="经理按利润与约束对两种方向统一评估后择优。",
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
                    conflict=f"各提案价格分歧较大（{spread_ratio:.1%}）。",
                    resolution="经理增加中间协调价并重新评估利润表现。",
                    priority="manager",
                )
            )
    return conflicts


def _manager_revision_prices(current_price: float, base_prices: Sequence[float]) -> List[float]:
    """生成经理额外复核时要尝试的一批中间候选价。"""
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
    """运行决策经理，综合三方提案后给出最终定价。"""
    current_price = max(float(request.product.current_price), 0.01)
    price_ceiling = request.risk_data.price_ceiling
    strategy_goal = (request.strategy_goal or "MAX_PROFIT").upper()
    market_live_available = bool(market_result.analysis_details.get("live_market_available"))
    warnings = list(risk_result.warnings[:3])

    # 先收集前三位智能体的建议价，必要时补一个经理中位协调价。
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

    # 所有提案都先过一次统一复核，避免不同智能体各自按不同口径比较。
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

    # 如果存在硬约束冲突或必须强制移动价格的场景，经理优先服从风控边界。
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
        key_factors = ["约束冲突", "人工复核"]
        warnings.append("约束冲突，无法给出安全可执行的自动调价结果。")
    elif mandatory_move:
        forced_price = float(risk_result.required_min_price)
        if risk_result.calculation_details.get("ceiling_breach") and price_ceiling is not None:
            forced_price = float(price_ceiling)
        chosen = _evaluate_agent_price(request, data_result, risk_result, forced_price)
        chosen["agent_name"] = "risk"
        key_factors = ["风险边界", "强制调价"]
    else:
        key_factors = ["三方提案", "经理协调", "利润校验"]
        candidate_pool = list(evaluated_proposals)
        if settings.market_live_required_for_discount and not market_live_available:
            candidate_pool = [item for item in candidate_pool if str(item["decision"]) != "discount"]
            warnings.append("实时市场数据不可用，已降低降价提案权重。")

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

        # 不同策略目标采用不同的选价逻辑：
        # 利润优先看利润提升，清仓优先看可执行降价，份额优先看市场份额增量。
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
                warnings.append("当前约束下未找到可执行且能提升利润的调价方案。")
        elif strategy_goal == "CLEARANCE":
            # Clearance objective should prioritize actionable markdown plans first.
            for rate in [0.9, 0.92, 0.94, 0.96, 0.98, 0.99]:
                revised = _evaluate_agent_price(request, data_result, risk_result, current_price * rate)
                revised["agent_name"] = "manager_revision"
                evaluated_proposals.append(revised)
                if not (
                    settings.market_live_required_for_discount
                    and not market_live_available
                    and str(revised["decision"]) == "discount"
                ):
                    candidate_pool.append(revised)

            discount_candidates = [item for item in candidate_pool if str(item["decision"]) == "discount"]
            if discount_candidates:
                chosen = min(
                    discount_candidates,
                    key=lambda item: (
                        float(item["suggested_price"]),
                        -float(item["market_share_change"]),
                        -float(item["profit_change"]),
                    ),
                )
            else:
                non_negative = [item for item in candidate_pool if float(item["profit_change"]) >= 0]
                chosen = min(non_negative or candidate_pool, key=lambda item: float(item["suggested_price"]))
                warnings.append("清仓目标下未找到可执行的降价方案，已回退为最低可行价格。")
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

    # 最后把选中的方案、冲突解释和预期收益汇总成最终报告。
    final_decision = str(chosen["decision"])
    final_price = float(chosen["suggested_price"])
    expected_outcomes = ExpectedOutcomes(
        sales_lift=float(chosen["sales_lift"]),
        profit_change=float(chosen["profit_change"]),
        market_share_change=float(chosen["market_share_change"]),
    )

    primary_agents = ["data", "market", "risk", "manager_midpoint"]
    proposal_items: List[Dict[str, Any]] = []
    for agent_name in primary_agents:
        item = next((row for row in evaluated_proposals if str(row.get("agent_name")) == agent_name), None)
        if item is not None:
            proposal_items.append(item)

    revision_items = [row for row in evaluated_proposals if str(row.get("agent_name")) == "manager_revision"]
    if revision_items:
        best_revision = max(revision_items, key=lambda row: float(row.get("profit_change", 0.0)))
        if str(chosen.get("agent_name")) == "manager_revision":
            best_revision = chosen
        proposal_items.append(best_revision)

    chosen_name = str(chosen.get("agent_name"))
    if chosen_name not in {str(item.get("agent_name")) for item in proposal_items}:
        proposal_items.append(chosen)

    proposal_text = "；".join(
        f"{_to_cn_agent_name(str(item['agent_name']))}建议价格为{float(item['suggested_price']):.2f}元（预计利润变化 {float(item['profit_change']):.2f}元）"
        for item in proposal_items
    )
    used_revision_result = str(chosen.get("agent_name")) == "manager_revision"
    revision_note = (
        f"经理额外复核了 {len(revision_items)} 个候选价格，并采纳了复核方案。"
        if revision_items and used_revision_result
        else ""
    )
    core_reasons = (
        "经理汇总数据分析、市场情报、风险控制三方独立提案，"
        f"完成冲突协调后采纳“{_to_cn_agent_name(str(chosen['agent_name']))}”方案。{proposal_text}"
        f"{revision_note}"
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
        "思考：经理比较三方提案并校验约束\n"
        f"推理：{core_reasons}\n"
        f"决策：{_to_cn_action(final_decision)}，建议价为 {final_price:.2f}元\n"
        f"冲突：{conflict_summary or '无'}"
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
        risk_warning=risk_result.veto_reason or ("风险可控" if risk_result.allow_promotion else "风险约束较强"),
        contingency_plan="若24小时内转化、毛利或退款指标恶化，立即回滚价格。",
        execution_plan=[
            ExecutionPlan(step=1, action=f"执行价格 {final_price:.2f}元", timing="立即", responsible="运营"),
            ExecutionPlan(step=2, action="跟踪转化率、毛利额和退款率", timing="24小时", responsible="分析师"),
        ],
        report_text=report_text,
        agent_summaries=[
            AgentSummary(agent_name="data", summary=data_result.decision_summary, key_points=data_result.recommendation_reasons[:3]),
            AgentSummary(agent_name="market", summary=market_result.decision_summary, key_points=market_result.suggestion_reasons[:3]),
            AgentSummary(agent_name="risk", summary=risk_result.decision_summary, key_points=risk_result.recommendation_reasons[:3]),
        ],
        decision_framework="三个业务智能体先提案，经理协调并裁决",
        alternative_options=[
            {"option": "维持当前价格", "discount_rate": 1.0},
            {"option": "风险底线价格", "discount_rate": round(float(risk_result.required_min_price) / current_price, 4)},
        ],
        thinking_process="三个业务智能体先独立给价，经理处理冲突后确定最终方案。",
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
