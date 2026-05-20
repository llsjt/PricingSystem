"""
CrewAI Crew 构建工厂
====================
根据定价任务的 Payload 动态生成 4 个 Task，
组装成一个顺序执行的 Crew，支持 Task 完成时的回调（用于实时写入卡片到数据库）。

优化：预计算数据摘要和竞品数据，直接注入到 prompt，
减少 Agent 的工具调用次数和 LLM 往返，大幅降低总耗时。
"""
# Crew 构造工厂，负责把 Agent、Task 和工具组装成一次定价编排实例。


from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from crewai import Agent, Crew, Process, Task

from app.agents.crewai_agents import build_crewai_agents
from app.core.config import get_settings
from app.crew.protocols import CrewRunPayload
from app.services.competitor_service import CompetitorService
from app.tools.elasticity_profit_tool import ElasticityProfitTool
from app.tools.product_data_tool import ProductDataTool
from app.tools.risk_rule_tool import RiskRuleTool
from app.utils.math_utils import money
from app.utils.text_utils import MANUAL_REVIEW_STRATEGY, to_strategy_goal_cn


@dataclass
class CrewBundle:
    """Crew 构建结果的结构化封装。

    在串行 Task 级调度（由 OrchestrationService 使用 task.execute_sync 驱动）场景下，
    OrchestrationService 直接按 order 拿 task + agent 执行；`crew` 字段保留兼容，
    便于未来需要时回退到 kickoff 模式。
    """

    crew: Crew
    tasks: list[Task]
    agents_by_order: dict[int, Agent]
    precomputed_competitor_summary: str | None = None


def _build_metrics_summary(payload: CrewRunPayload) -> str:
    """将近30天经营指标压缩为简洁的文本摘要"""
    if not payload.metrics:
        return "暂无近30天经营数据"

    total_sales = sum(m.sales_count for m in payload.metrics)
    total_turnover = sum(m.turnover for m in payload.metrics)
    total_visitors = sum(m.visitor_count for m in payload.metrics)
    avg_conv = (
        sum(m.conversion_rate for m in payload.metrics) / len(payload.metrics)
        if payload.metrics
        else Decimal("0")
    )

    return (
        f"近{len(payload.metrics)}天数据: "
        f"总销量={total_sales}件, 总营业额={money(total_turnover)}元, "
        f"总访客={total_visitors}人, 平均转化率={avg_conv:.4f}"
    )


def _build_constraints_text(constraints: dict) -> str:
    """将约束条件字典转换为可读文本"""
    if not constraints:
        return "最低利润率15%（默认）"

    parts = []
    if "min_profit_rate" in constraints:
        parts.append(f"最低利润率{float(constraints['min_profit_rate'])*100:.0f}%")
    if "min_price" in constraints:
        parts.append(f"最低售价{constraints['min_price']}元")
    if "max_price" in constraints:
        parts.append(f"最高售价{constraints['max_price']}元")
    if "max_discount_rate" in constraints:
        parts.append(f"最大降价幅度{float(constraints['max_discount_rate'])*100:.0f}%")
    if constraints.get("force_manual_review"):
        parts.append("强制人工审核")

    return "，".join(parts) if parts else "最低利润率15%（默认）"


def _precompute_data_summary(payload: CrewRunPayload) -> str:
    """预计算商品数据汇总，转为紧凑文本直接注入 prompt（免去 Agent 调工具）"""
    tool = ProductDataTool()
    result = tool.summarize(
        product=payload.product,
        metrics=payload.metrics,
        traffic=payload.traffic,
    )
    lines = [
        f"月销量: {result.get('monthly_sales', 0)}件",
        f"月营业额: {result.get('monthly_turnover', 0)}元",
        f"平均转化率: {result.get('average_conversion_rate', 0)}",
        f"总访客: {result.get('total_visitors', 0)}人",
        f"流量点击率(CTR): {result.get('traffic_ctr', 0)}",
        f"当前售价: {result.get('current_price', 0)}元",
        f"成本价: {result.get('cost_price', 0)}元",
        f"库存: {result.get('stock', 0)}件",
    ]
    return "\n".join(lines)


def _decimal_or_zero(value: Any) -> Decimal:
    try:
        return Decimal(str(value if value is not None else "0"))
    except Exception:
        return Decimal("0")


def _bounded_profit_rate(constraints: dict) -> Decimal:
    raw = _decimal_or_zero(constraints.get("min_profit_rate", "0.15"))
    if raw < 0:
        return Decimal("0")
    if raw >= Decimal("0.95"):
        return Decimal("0.95")
    return raw


def _strategy_candidate_price(payload: CrewRunPayload) -> Decimal:
    """按策略先给一个确定性候选价，避免 Agent 通过工具循环反复试价。"""
    current = money(payload.product.current_price)
    cost = money(payload.product.cost_price)
    strategy = str(payload.strategy_goal or "").upper()
    if strategy == "CLEARANCE":
        multiplier = Decimal("0.95")
    elif strategy == "MARKET_SHARE":
        multiplier = Decimal("0.97")
    else:
        multiplier = Decimal("1.03")

    candidate = money(current * multiplier)
    min_profit_rate = _bounded_profit_rate(payload.constraints or {})
    profit_floor = cost / (Decimal("1.0") - min_profit_rate) if min_profit_rate < 1 else cost
    candidate = max(candidate, money(cost * Decimal("1.08")), money(profit_floor))

    min_price = (payload.constraints or {}).get("min_price")
    if min_price is not None:
        candidate = max(candidate, money(min_price))
    max_price = (payload.constraints or {}).get("max_price")
    if max_price is not None:
        candidate = min(candidate, money(max_price))
    return money(candidate)


def _precompute_data_projection(payload: CrewRunPayload) -> str:
    """预计算销量和利润，让数据分析 Agent 一轮生成解释，不再进入工具调用循环。"""
    tool = ElasticityProfitTool()
    current = money(payload.product.current_price)
    cost = money(payload.product.cost_price)
    candidate = _strategy_candidate_price(payload)
    expected_sales = tool.estimate_sales(
        baseline_sales=int(payload.baseline_sales or 0),
        current_price=current,
        target_price=candidate,
        strategy_goal=str(payload.strategy_goal or ""),
    )
    expected_profit = tool.estimate_profit(
        price=candidate,
        cost_price=cost,
        expected_sales=expected_sales,
    )

    min_price = money(max(cost * Decimal("1.08"), candidate * Decimal("0.97")))
    max_price = money(max(min_price, candidate * Decimal("1.03")))
    constraints = payload.constraints or {}
    if constraints.get("min_price") is not None:
        min_price = max(min_price, money(constraints["min_price"]))
    if constraints.get("max_price") is not None:
        max_price = min(max_price, money(constraints["max_price"]))
    if max_price < min_price:
        max_price = min_price

    lines = [
        "预计算销量/利润测算结果:",
        f"- 候选建议价: {candidate}元",
        f"- 建议价格区间: {min_price}元 - {max_price}元",
        f"- 预期月销量 expectedSales: {expected_sales}",
        f"- 预期月利润 expectedProfit: {expected_profit}元",
        "- 以上数值已由 Python 确定性测算完成，请直接用于 JSON 输出并解释原因。",
    ]
    return "\n".join(lines)


def _precompute_risk_projection(payload: CrewRunPayload) -> str:
    """预计算硬约束风控结果，让风控 Agent 不再通过工具循环校验。"""
    current = money(payload.product.current_price)
    cost = money(payload.product.cost_price)
    candidate = _strategy_candidate_price(payload)
    constraints = dict(payload.constraints or {})
    constraints.setdefault("min_profit_rate", 0.15)
    constraints.setdefault("max_discount_rate", 0.5)
    result = RiskRuleTool().evaluate(
        current_price=current,
        cost_price=cost,
        candidate_price=candidate,
        constraints=constraints,
    )
    lines = [
        "预计算风控校验结果:",
        f"- 候选价: {candidate}元",
        f"- 安全底价 safeFloorPrice: {result.get('safe_floor_price')}元",
        f"- 风控建议价 suggestedPrice: {result.get('suggested_price')}元",
        f"- 是否通过 isPass: {result.get('is_pass')}",
        f"- 风险等级 riskLevel: {result.get('risk_level')}",
        f"- 是否需要人工审核 needManualReview: {result.get('need_manual_review')}",
        f"- 预估毛利率 margin: {result.get('margin')}",
        "- 以上结果已由 Python 硬约束规则计算完成，请直接用于 JSON 输出并解释原因。",
    ]
    return "\n".join(lines)


def _precompute_competitor_summary(payload: CrewRunPayload) -> str:
    """预计算竞品数据，转为紧凑文本直接注入 prompt（免去 Agent 调工具）"""
    service = CompetitorService()
    result = service.get_competitor_result(
        product_id=payload.product.product_id,
        product_title=payload.product.product_name,
        category_name=payload.product.category_name,
        current_price=payload.product.current_price,
    )
    competitors = result.get("competitors", []) or []
    source = str(result.get("source", "UNKNOWN"))
    status = str(result.get("sourceStatus", "FAILED"))
    message = str(result.get("message", ""))
    raw_item_count = int(result.get("rawItemCount", 0) or 0)
    filtered_item_count = int(result.get("filteredItemCount", len(competitors)) or 0)
    valid_competitor_count = int(result.get("validCompetitorCount", len(competitors)) or 0)
    market_floor = float(result.get("marketFloor", 0) or 0)
    market_median = float(result.get("marketMedian", 0) or 0)
    market_ceiling = float(result.get("marketCeiling", 0) or 0)
    market_average = float(result.get("marketAverage", 0) or 0)
    data_quality = str(result.get("dataQuality", "LOW"))
    quality_reasons = list(result.get("qualityReasons") or [])
    competitor_samples = len(competitors)
    no_real_competitor_data = status.upper() != "OK" or competitor_samples == 0
    min_valid_count = max(int(get_settings().market_competitor_min_valid_count), 1)
    low_quality = status.upper() == "OK" and 0 < valid_competitor_count < min_valid_count

    lines = [
        f"竞品来源: {source}",
        f"竞品状态: {status}",
        f"状态说明: {message}",
        f"原始样本数: {raw_item_count}",
        f"竞品样本数: {competitor_samples}",
    ]
    lines.extend(
        [
            f"筛选后样本数: {filtered_item_count}",
            f"有效样本数: {valid_competitor_count}",
            f"数据质量: {data_quality}",
        ]
    )
    if quality_reasons:
        lines.append(f"质量原因: {', '.join(str(item) for item in quality_reasons)}")

    if no_real_competitor_data:
        lines.extend(
            [
                "无有效竞品时的硬规则：",
                "- sourceStatus != OK 或 competitorSamples == 0 时，不得推断或编造市场最低价、最高价、均价。",
                "- suggestedPrice 输出 0。",
                "- competitorSamples 输出 0。",
                "- marketFloor 与 marketCeiling 输出 0。",
                "- confidence 必须 <= 0.3。",
                "- summary 必须明确说明竞品状态和原因。",
            ]
        )
    if not competitors:
        lines.append("竞品明细: 无")
        return "\n".join(lines)

    # 计算竞品统计
    if low_quality:
        lines.extend(
            [
                "低质量样本时的硬规则：",
                f"- validCompetitorCount < {min_valid_count} 时，不得输出激进的市场结论。",
                "- 优先给出保守区间，不要给出过强的单点结论。",
                "- 如果输出 suggestedPrice，confidence 必须 <= 0.6。",
            ]
        )

    prices = [float(c["price"]) for c in competitors if c.get("price") is not None]
    min_price = market_floor or (min(prices) if prices else 0.0)
    max_price = market_ceiling or (max(prices) if prices else 0.0)
    avg_price = market_average or (sum(prices) / len(prices) if prices else 0.0)
    lines.append(f"市场中位价: {market_median:.2f}元")
    lines.extend(
        [
            f"市场最低价: {min_price:.2f}元",
            f"市场最高价: {max_price:.2f}元",
            f"市场均价: {avg_price:.2f}元",
        ]
    )

    sales_weighted_avg = result.get("salesWeightedAverage")
    sales_weighted_median = result.get("salesWeightedMedian")
    if sales_weighted_avg is not None:
        lines.append(f"销量加权均价: {float(sales_weighted_avg):.2f}元")
    if sales_weighted_median is not None:
        lines.append(f"销量加权中位价: {float(sales_weighted_median):.2f}元")

    brand_breakdown = result.get("brandBreakdown") or []
    if brand_breakdown:
        lines.append("品牌价格带 (top 5):")
        for band in brand_breakdown[:5]:
            lines.append(
                f"  - {band.get('brand', '未知')} | 样本{int(band.get('sampleCount', 0))}件 | "
                f"均价{float(band.get('averagePrice', 0)):.2f}元 | "
                f"价格区间{float(band.get('minPrice', 0)):.2f}-{float(band.get('maxPrice', 0)):.2f}元"
            )

    shop_type_breakdown = result.get("shopTypeBreakdown") or []
    if shop_type_breakdown:
        lines.append("店铺类型分布:")
        for band in shop_type_breakdown[:5]:
            share_pct = float(band.get("share", 0)) * 100
            lines.append(
                f"  - {band.get('shopType', '其他')} | 占比{share_pct:.1f}% | "
                f"均价{float(band.get('averagePrice', 0)):.2f}元"
            )

    promotion_density = result.get("promotionDensity") or {}
    if promotion_density:
        rate = promotion_density.get("promotionRate")
        avg_discount = promotion_density.get("averageDiscount")
        promoted = promotion_density.get("promotedSampleCount")
        density_parts = []
        if rate is not None:
            density_parts.append(f"促销占比{float(rate) * 100:.1f}%")
        if promoted is not None:
            density_parts.append(f"在促样本{int(promoted)}件")
        if avg_discount is not None:
            density_parts.append(f"平均折扣率{float(avg_discount):.2f}")
        if density_parts:
            lines.append("促销密度: " + " | ".join(density_parts))

    lines.append("竞品明细:")
    for c in competitors[:5]:  # 最多展示5条，避免 prompt 过长
        line = f"  - {c.get('competitorName', '未知')}"
        if c.get("price") is not None:
            line += f" | 价格{float(c['price']):.2f}元"
        if c.get("shopType"):
            line += f" | {c['shopType']}"
        if c.get("salesVolumeHint"):
            line += f" | {c['salesVolumeHint']}"
        if c.get("promotionTag"):
            line += f" | {c['promotionTag']}"
        lines.append(line)

    return "\n".join(lines)


def build_pricing_crew(
    payload: CrewRunPayload,
    analysis_llm: object,
    manager_llm: object,
    on_task_done: Callable | None = None,
    include_competitor_summary: bool = True,
) -> CrewBundle:
    """
    构建定价决策 Crew。

    优化策略：预计算数据摘要和竞品数据并注入 prompt，
    减少 Agent 的工具调用轮次，降低 LLM 往返次数。

    返回 CrewBundle 以便调用方按 Task 粒度调度执行
    （支持失败重试时只重跑失败 Agent 及其下游）。
    """
    # ── 创建 4 个 Agent ────────────────────────────────────
    agents = build_crewai_agents(analysis_llm=analysis_llm, manager_llm=manager_llm)

    # ── 预计算数据摘要（免去 Agent 调用汇总工具） ─────────
    product = payload.product
    strategy_cn = to_strategy_goal_cn(payload.strategy_goal)
    metrics_summary = _build_metrics_summary(payload)
    constraints_text = _build_constraints_text(payload.constraints)
    data_summary = _precompute_data_summary(payload)
    data_projection = _precompute_data_projection(payload)
    competitor_summary = (
        _precompute_competitor_summary(payload)
        if include_competitor_summary
        else "本轮复用历史 MARKET_INTEL 输出，未重新计算竞品摘要。"
    )
    risk_projection = _precompute_risk_projection(payload)

    # ── Task 1: 数据分析任务 ──────────────────────────────
    # 数据与测算结果已预计算，Agent 只需解释和结构化输出。
    data_task = Task(
        description=(
            f"你正在为商品「{product.product_name}」制定定价策略。\n"
            f"策略目标: {strategy_cn}\n"
            f"基线月销量: {payload.baseline_sales}件，基线月利润: {money(payload.baseline_profit)}元\n\n"
            "以下是商品经营数据汇总（已预计算）：\n"
            f"{data_summary}\n"
            f"{metrics_summary}\n\n"
            "以下是预计算销量/利润测算结果（Python 已执行确定性测算）：\n"
            f"{data_projection}\n\n"
            "请基于以上数据分析：\n"
            "1. 评估销售趋势（上升/下降/平稳）\n"
            "2. 根据策略目标确定建议价格：\n"
            "   - 利润优先：适当提价（+1%~4%）\n"
            "   - 清仓促销：适当降价（-5%左右）\n"
            "   - 市场份额优先：小幅降价（-3%左右）\n"
            "3. 直接采用预计算的候选建议价、expectedSales、expectedProfit 和建议价格区间\n"
            "4. 解释这些数值与策略目标、成本和基线利润之间的关系\n\n"
            "最终输出必须是严格的JSON格式，包含以下字段："
        ),
        expected_output=(
            "严格JSON格式输出，字段如下：\n"
            '{"suggestedPrice": 建议价格(数字), '
            '"suggestedMinPrice": 建议最低价(数字), '
            '"suggestedMaxPrice": 建议最高价(数字), '
            '"expectedSales": 预期月销量(整数), '
            '"expectedProfit": 预期月利润(数字), '
            '"confidence": 置信度(0-1之间的小数), '
            '"thinking": "你的分析思路(中文)", '
            '"summary": "分析摘要(中文字符串)"}'
        ),
        agent=agents["DATA_ANALYSIS"],
        callback=on_task_done,
    )

    # ── Task 2: 市场情报任务（独立执行，不依赖其他 Agent） ──
    market_task = Task(
        description=(
            f"你正在为商品「{product.product_name}」分析市场竞争态势。\n"
            f"品类: {product.category_name or '通用品类'}，当前售价: {money(product.current_price)}元\n"
            f"策略目标: {strategy_cn}\n\n"
            "以下是竞品价格数据（已预获取）：\n"
            f"{competitor_summary}\n\n"
            "请基于以上竞品数据分析：\n"
            "1. 识别市场价格带：地板价、天花板价、均价\n"
            "2. 评估促销压力和竞争强度\n"
            "3. 根据策略目标给出市场建议价格：\n"
            "   - 利润优先：可略高于市场均价\n"
            "   - 清仓促销：接近市场地板价\n"
            "   - 市场份额优先：接近市场均价\n\n"
            "硬规则（必须严格执行）：\n"
            "- sourceStatus != OK 时，不得编造市场价格带，建议价必须保守并在summary中说明原因。\n"
            "- validCompetitorCount < 3 时，不得输出强建议价；只能输出风险提示和弱建议。\n"
            "- dataQuality = LOW 时，confidence 不得高于 0.6。\n"
            "- 所有面向用户的自然语言字段必须使用中文，包括 thinking、summary、riskNotes、evidenceSummary、qualityReasons。\n"
            "- 同一事实不得在 summary、evidenceSummary、riskNotes 中重复表述；结论、证据、风险、动作各说一次即可。\n"
            "- validCompetitorCount 是唯一必须输出的样本量字段，不要输出 rawItemCount、filteredItemCount、competitorSamples、usedCompetitorCount。\n"
            "- 不要输出 pricingPosition、salesWeightedAverage、salesWeightedMedian、shopTypeBreakdown，这些字段不再作为默认展示契约的一部分。\n"
            "最终输出必须是严格的JSON格式："
        ),
        expected_output=(
            "严格JSON格式输出，字段如下：\n"
            '{"suggestedPrice": 市场建议价格(数字), '
            '"marketFloor": 市场最低价(数字), '
            '"marketCeiling": 市场最高价(数字), '
            '"marketMedian": 市场中位价(数字), '
            '"marketAverage": 市场均价(数字), '
            '"confidence": 置信度(0-1之间的小数), '
            '"thinking": "你的分析思路(中文)", '
            '"summary": "市场分析摘要(中文字符串)", '
            '"validCompetitorCount": 有效竞品数(整数), '
            '"dataQuality": "HIGH/MEDIUM/LOW", '
            '"qualityReasons": ["质量原因"], '
            '"riskNotes": "风险提示(中文，可空)", '
            '"evidenceSummary": "证据摘要(中文，可空)", '
            '"brandBreakdown": [{"brand": "品牌", "sampleCount": 样本数, "averagePrice": 均价, "medianPrice": 中位价, "minPrice": 最低价, "maxPrice": 最高价}], '
            '"promotionDensity": {"promotionRate": 促销占比, "averageDiscount": 平均折扣率, "promotedSampleCount": 在促样本数}, '
            '"source": "竞品来源", '
            '"sourceStatus": "竞品状态"}'
        ),
        agent=agents["MARKET_INTEL"],
        callback=on_task_done,
    )

    # ── Task 3: 风险控制任务（独立执行，不依赖其他 Agent） ──
    risk_task = Task(
        description=(
            f"你正在为商品「{product.product_name}」的定价方案进行风险评估。\n"
            f"当前售价: {money(product.current_price)}元，成本价: {money(product.cost_price)}元\n"
            f"策略目标: {strategy_cn}\n"
            f"约束条件: {constraints_text}\n\n"
            "以下是预计算风控校验结果（Python 已执行硬约束规则）：\n"
            f"{risk_projection}\n\n"
            "请按以下步骤操作：\n"
            "1. 核对预计算的候选价、成本底线、最低利润率和上下限约束\n"
            "2. 直接采用预计算的 safeFloorPrice、风控建议价、isPass、riskLevel 和 needManualReview\n"
            "3. 用中文解释为什么该价格通过或不通过风控\n\n"
            "最终输出必须是严格的JSON格式："
        ),
        expected_output=(
            "严格JSON格式输出，字段如下：\n"
            '{"isPass": 是否通过风控(true/false), '
            '"safeFloorPrice": 安全底价(数字), '
            '"suggestedPrice": 风控建议价(数字), '
            '"riskLevel": "LOW或HIGH", '
            '"needManualReview": 是否需人工复核(true/false), '
            '"thinking": "你的分析思路(中文)", '
            '"summary": "风控评估摘要(中文字符串)"}'
        ),
        agent=agents["RISK_CONTROL"],
        callback=on_task_done,
    )

    # ── Task 4: 经理协调任务 ──────────────────────────────
    manager_task = Task(
        description=(
            f"你是商品「{product.product_name}」定价决策的最终负责人。\n"
            f"当前售价: {money(product.current_price)}元，成本价: {money(product.cost_price)}元\n"
            f"策略目标: {strategy_cn}\n"
            f"基线月销量: {payload.baseline_sales}件，基线月利润: {money(payload.baseline_profit)}元\n\n"
            "请综合前面三个专家的分析结果：\n"
            "1. 数据分析专家的建议价格和预期利润\n"
            "2. 市场情报分析师的市场建议价格和价格区间\n"
            "3. 风控专家的安全评估和风控建议价\n\n"
            "决策规则：\n"
            "- 最终价格必须不低于风控的安全底价\n"
            "- 最终价格必须不高于市场天花板价\n"
            "- 使用 estimate_sales_volume 和 estimate_profit 工具验证最终价格的预期效果\n"
            f'  (baseline_sales={payload.baseline_sales}, current_price="{money(product.current_price)}", '
            f'cost_price="{money(product.cost_price)}", strategy_goal="{payload.strategy_goal}")\n\n'
            "执行策略要求：\n"
            f"- 所有定价结果都必须进入「{MANUAL_REVIEW_STRATEGY}」流程，不允许直接执行或灰度发布。\n"
            f'- 输出 JSON 的 executeStrategy 字段必须固定为「{MANUAL_REVIEW_STRATEGY}」。\n\n'
            "请使用规范仲裁字段说明为什么采纳或不采纳每个专家的建议，给出清晰的决策理由。\n"
            "- 仅使用 disagreementSummary、disagreementPoints、acceptedOpinions、rejectedOpinions、"
            "arbitrationDecision、arbitrationReason、selectedAgent、selectedPrice、selectedStrategy、consensusScore。\n"
            "- 仅输出上面列出的规范仲裁字段，不要补充历史别名字段。\n"
            "- consensusScore 使用 0 到 1 之间的小数，不要使用百分比。\n"
            "- selectedPrice 表示被采纳的上游意见价格，不一定等于 finalPrice。\n"
            "- 如果最终结果是折中价，selectedAgent 和 selectedPrice 可以为 null，但 arbitrationReason 必须解释折中逻辑。\n\n"
            "最终输出必须是严格的JSON格式："
            "不得引用不存在的 opinionId。\n"
        ),
        expected_output=(
            "严格JSON格式输出，字段如下：\n"
            '{"finalPrice": 最终建议价格(数字), '
            '"expectedSales": 预期月销量(整数), '
            '"expectedProfit": 预期月利润(数字), '
            '"profitGrowth": 利润变化额(数字,可为负), '
            f'"executeStrategy": "{MANUAL_REVIEW_STRATEGY}", '
            '"isPass": 是否建议执行(true/false), '
            '"thinking": "你的决策思路(中文)", '
            '"resultSummary": "综合决策摘要(中文字符串,包含对各专家意见的采纳理由)", '
            '"suggestedMinPrice": 建议最低价(数字), '
            '"suggestedMaxPrice": 建议最高价(数字), '
            '"consensusScore": 共识度(0-1之间小数,可选), '
            '"disagreementSummary": "主要分歧摘要(可选)", '
            '"disagreementPoints": ["分歧点1", "分歧点2"], '
            '"acceptedOpinions": ["采纳意见1"], '
            '"rejectedOpinions": ["未采纳意见1"], '
            '"arbitrationDecision": "最终裁决结论(可选)", '
            '"arbitrationReason": "裁决理由(可选)", '
            '"selectedAgent": "DATA_ANALYSIS/MARKET_INTEL/RISK_CONTROL/null", '
            '"selectedPrice": 被采纳意见价格(数字或null), '
            '"selectedStrategy": "被采纳方案策略(可选)"}'
            '\nMust also include "agentOpinion" with "relations" and "decision". The relations object must include "dependsOnOpinionIds", "acceptedOpinionIds", "rejectedOpinionIds", and "selectedOpinionIds". The decision object must include "decisionType", "consensusScore", "arbitrationDecision", and "arbitrationReason".'
        ),
        agent=agents["MANAGER_COORDINATOR"],
        context=[data_task, market_task, risk_task],
        callback=on_task_done,
    )

    # ── 组装 Crew（顺序执行流程） ─────────────────────────
    # Crew 仍保留，便于将来回退到 kickoff 模式或调试，但
    # OrchestrationService 在正常路径上通过 CrewBundle.tasks/agents_by_order
    # 直接调用 task.execute_sync，以支持 Agent 粒度的断点续跑。
    crew = Crew(
        agents=[
            agents["DATA_ANALYSIS"],
            agents["MARKET_INTEL"],
            agents["RISK_CONTROL"],
            agents["MANAGER_COORDINATOR"],
        ],
        tasks=[data_task, market_task, risk_task, manager_task],
        process=Process.sequential,
        verbose=True,
    )

    return CrewBundle(
        crew=crew,
        tasks=[data_task, market_task, risk_task, manager_task],
        agents_by_order={
            1: agents["DATA_ANALYSIS"],
            2: agents["MARKET_INTEL"],
            3: agents["RISK_CONTROL"],
            4: agents["MANAGER_COORDINATOR"],
        },
        precomputed_competitor_summary=competitor_summary if include_competitor_summary else None,
    )
