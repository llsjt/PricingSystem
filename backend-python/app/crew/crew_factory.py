"""
CrewAI Crew 构建工厂
====================
根据定价任务的 Payload 动态生成 4 个 Task，
组装成一个顺序执行的 Crew，支持 Task 完成时的回调（用于实时写入卡片到数据库）。

优化：预计算数据摘要和竞品数据，直接注入到 prompt，
减少 Agent 的工具调用次数和 LLM 往返，大幅降低总耗时。
"""

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from crewai import Crew, Process, Task

from app.agents.crewai_agents import build_crewai_agents
from app.core.config import get_settings
from app.crew.protocols import CrewRunPayload
from app.services.competitor_service import CompetitorService
from app.tools.product_data_tool import ProductDataTool
from app.utils.math_utils import money
from app.utils.text_utils import MANUAL_REVIEW_STRATEGY, to_strategy_goal_cn


def _serialize_decimal(obj: Any) -> Any:
    """JSON 序列化时将 Decimal 转为 str"""
    if isinstance(obj, Decimal):
        return str(obj)
    return str(obj)


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
                "NO_DATA_RULES:",
                "- sourceStatus != OK or competitorSamples == 0: do not infer or fabricate market floor/ceiling/average.",
                "- Output suggestedPrice=0.",
                "- Output competitorSamples=0.",
                "- Set marketFloor=0 and marketCeiling=0.",
                "- Keep confidence <= 0.3.",
                "- summary must explicitly include provider status and reason.",
            ]
        )
    if not competitors:
        lines.append("竞品明细: 无")
        return "\n".join(lines)

    # 计算竞品统计
    if low_quality:
        lines.extend(
            [
                "LOW_DATA_RULES:",
                f"- validCompetitorCount < {min_valid_count}: do not output an aggressive market conclusion.",
                "- Prefer a conservative range over a strong single-price recommendation.",
                "- If suggestedPrice is present, keep confidence <= 0.6.",
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
            "竞品明细:",
        ]
    )
    for c in competitors[:5]:  # 最多展示5条，避免 prompt 过长
        line = f"  - {c.get('competitorName', '未知')}"
        if c.get("price") is not None:
            line += f" | 价格{float(c['price']):.2f}元"
        if c.get("sourcePlatform"):
            line += f" | {c['sourcePlatform']}"
        if c.get("promotionTag"):
            line += f" | {c['promotionTag']}"
        lines.append(line)

    return "\n".join(lines)


def build_pricing_crew(
    payload: CrewRunPayload,
    analysis_llm: object,
    manager_llm: object,
    on_task_done: Callable | None = None,
) -> Crew:
    """
    构建定价决策 Crew。

    优化策略：预计算数据摘要和竞品数据并注入 prompt，
    减少 Agent 的工具调用轮次，降低 LLM 往返次数。
    """
    # ── 创建 4 个 Agent ────────────────────────────────────
    agents = build_crewai_agents(analysis_llm=analysis_llm, manager_llm=manager_llm)

    # ── 预计算数据摘要（免去 Agent 调用汇总工具） ─────────
    product = payload.product
    strategy_cn = to_strategy_goal_cn(payload.strategy_goal)
    metrics_summary = _build_metrics_summary(payload)
    constraints_text = _build_constraints_text(payload.constraints)
    data_summary = _precompute_data_summary(payload)
    competitor_summary = _precompute_competitor_summary(payload)

    # ── Task 1: 数据分析任务 ──────────────────────────────
    # 数据已预计算，Agent 只需分析摘要 + 调用销量/利润预估工具
    data_task = Task(
        description=(
            f"你正在为商品「{product.product_name}」制定定价策略。\n"
            f"策略目标: {strategy_cn}\n"
            f"基线月销量: {payload.baseline_sales}件，基线月利润: {money(payload.baseline_profit)}元\n\n"
            "以下是商品经营数据汇总（已预计算）：\n"
            f"{data_summary}\n"
            f"{metrics_summary}\n\n"
            "请基于以上数据分析：\n"
            "1. 评估销售趋势（上升/下降/平稳）\n"
            "2. 根据策略目标确定建议价格：\n"
            "   - 利润优先：适当提价（+1%~4%）\n"
            "   - 清仓促销：适当降价（-5%左右）\n"
            "   - 市场份额优先：小幅降价（-3%左右）\n"
            "3. 使用「预估调价后销量」工具计算预期销量\n"
            f'   参数: {{"baseline_sales": {payload.baseline_sales}, "current_price": "{money(product.current_price)}", '
            f'"target_price": "你的建议价格", "strategy_goal": "{payload.strategy_goal}"}}\n'
            "4. 使用「预估利润」工具计算预期利润\n"
            f'   参数: {{"price": "你的建议价格", "cost_price": "{money(product.cost_price)}", "expected_sales": 预估销量}}\n'
            "5. 确定建议价格区间（最低价不低于成本价×1.08）\n\n"
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
            "- 所有结论必须引用给定统计值，不允许重新虚构样本。\n\n"
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
            '"competitorSamples": 竞品样本数(整数), '
            '"rawItemCount": 原始样本数(整数), '
            '"filteredItemCount": 过滤后样本数(整数), '
            '"validCompetitorCount": 有效竞品数(整数), '
            '"dataQuality": "HIGH/MEDIUM/LOW", '
            '"qualityReasons": ["质量原因"], '
            '"pricingPosition": "当前价格相对市场位置说明", '
            '"usedCompetitorCount": 纳入分析的有效竞品数(整数), '
            '"riskNotes": "风险提示(中文，可空)", '
            '"evidenceSummary": "证据摘要(中文，可空)", '
            '"source": "竞品来源", '
            '"sourceStatus": "竞品状态"}'
        ),
        agent=agents["MARKET_INTEL"],
        callback=on_task_done,
    )

    # ── Task 3: 风险控制任务（独立执行，不依赖其他 Agent） ──
    # 构建风控工具参数提示
    risk_tool_params = (
        f'"current_price": {float(money(product.current_price))}, '
        f'"cost_price": {float(money(product.cost_price))}, '
        '"candidate_price": 你确定的候选价格'
    )
    min_pr = float(payload.constraints.get("min_profit_rate", 0.15))
    risk_tool_params += f', "min_profit_rate": {min_pr}'
    max_dr = payload.constraints.get("max_discount_rate")
    if max_dr is not None:
        risk_tool_params += f', "max_discount_rate": {float(max_dr)}'
    min_p = payload.constraints.get("min_price")
    if min_p is not None:
        risk_tool_params += f', "min_price": {float(min_p)}'
    max_p = payload.constraints.get("max_price")
    if max_p is not None:
        risk_tool_params += f', "max_price": {float(max_p)}'

    risk_task = Task(
        description=(
            f"你正在为商品「{product.product_name}」的定价方案进行风险评估。\n"
            f"当前售价: {money(product.current_price)}元，成本价: {money(product.cost_price)}元\n"
            f"策略目标: {strategy_cn}\n"
            f"约束条件: {constraints_text}\n\n"
            "请按以下步骤操作：\n"
            "1. 根据策略目标确定一个候选价格：\n"
            "   - 利润优先：当前售价上浮2%左右\n"
            "   - 清仓促销：当前售价下调5%左右\n"
            "   - 市场份额优先：当前售价下调3%左右\n"
            "2. 使用「评估风控规则」工具校验候选价格，参数如下：\n"
            f"   {{{risk_tool_params}}}\n"
            "3. 根据工具返回结果，判断候选价格是否安全\n"
            "4. 如果候选价格不通过，使用工具返回的suggested_price作为风控建议价\n\n"
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
            "- 使用「预估调价后销量」和「预估利润」工具验证最终价格的预期效果\n"
            f'  (baseline_sales={payload.baseline_sales}, current_price="{money(product.current_price)}", '
            f'cost_price="{money(product.cost_price)}", strategy_goal="{payload.strategy_goal}")\n\n'
            "执行策略要求：\n"
            f"- 所有定价结果都必须进入「{MANUAL_REVIEW_STRATEGY}」流程，不允许直接执行或灰度发布。\n"
            f'- 输出 JSON 的 executeStrategy 字段必须固定为「{MANUAL_REVIEW_STRATEGY}」。\n\n'
            "请说明为什么采纳或不采纳每个专家的建议，给出清晰的决策理由。\n\n"
            "最终输出必须是严格的JSON格式："
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
            '"suggestedMaxPrice": 建议最高价(数字)}'
        ),
        agent=agents["MANAGER_COORDINATOR"],
        context=[data_task, market_task, risk_task],
        callback=on_task_done,
    )

    # ── 组装 Crew（顺序执行流程） ─────────────────────────
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

    return crew
