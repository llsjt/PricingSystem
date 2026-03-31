"""
CrewAI Crew 构建工厂
====================
根据定价任务的 Payload 动态生成 4 个 Task，
组装成一个顺序执行的 Crew，支持 Task 完成时的回调（用于实时写入卡片到数据库）。

优化：预计算数据摘要和竞品数据，直接注入到 prompt，
减少 Agent 的工具调用次数和 LLM 往返，大幅降低总耗时。
"""

import json
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from crewai import Crew, Process, Task

from app.agents.crewai_agents import build_crewai_agents
from app.crew.protocols import CrewRunPayload
from app.services.competitor_service import CompetitorService
from app.tools.product_data_tool import ProductDataTool
from app.utils.math_utils import money
from app.utils.text_utils import to_strategy_goal_cn


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
    competitors = service.get_competitors(
        product_id=payload.product.product_id,
        product_title=payload.product.product_name,
        category_name=payload.product.category_name,
        current_price=payload.product.current_price,
    )
    if not competitors:
        return "暂无竞品数据"

    # 计算竞品统计
    prices = [c["price"] for c in competitors if c.get("price")]
    min_price = min(prices) if prices else 0
    max_price = max(prices) if prices else 0
    avg_price = sum(prices) / len(prices) if prices else 0

    lines = [
        f"竞品样本数: {len(competitors)}",
        f"市场最低价: {min_price:.2f}元",
        f"市场最高价: {max_price:.2f}元",
        f"市场均价: {avg_price:.2f}元",
        "竞品明细:",
    ]
    for c in competitors[:5]:  # 最多展示5条，避免 prompt 过长
        line = f"  - {c.get('competitorName', '未知')}"
        line += f" | 价格{c['price']:.2f}元"
        if c.get("sourcePlatform"):
            line += f" | {c['sourcePlatform']}"
        if c.get("promotionTag"):
            line += f" | {c['promotionTag']}"
        lines.append(line)

    return "\n".join(lines)


def build_pricing_crew(
    payload: CrewRunPayload,
    llm: object,
    on_task_done: Callable | None = None,
) -> Crew:
    """
    构建定价决策 Crew。

    优化策略：预计算数据摘要和竞品数据并注入 prompt，
    减少 Agent 的工具调用轮次，降低 LLM 往返次数。
    """
    # ── 创建 4 个 Agent ────────────────────────────────────
    agents = build_crewai_agents(llm)

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

    # ── Task 2: 市场情报任务 ──────────────────────────────
    # 竞品数据已预计算，Agent 无需调用工具，直接分析给出建议
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
            "同时参考上一步数据分析Agent的结果进行综合判断。\n\n"
            "最终输出必须是严格的JSON格式："
        ),
        expected_output=(
            "严格JSON格式输出，字段如下：\n"
            '{"suggestedPrice": 市场建议价格(数字), '
            '"marketFloor": 市场最低价(数字), '
            '"marketCeiling": 市场最高价(数字), '
            '"confidence": 置信度(0-1之间的小数), '
            '"thinking": "你的分析思路(中文)", '
            '"summary": "市场分析摘要(中文字符串)", '
            '"simulatedSamples": 竞品样本数(整数)}'
        ),
        agent=agents["MARKET_INTEL"],
        context=[data_task],
        callback=on_task_done,
    )

    # ── Task 3: 风险控制任务 ──────────────────────────────
    risk_task = Task(
        description=(
            f"你正在为商品「{product.product_name}」的定价方案进行风险评估。\n"
            f"当前售价: {money(product.current_price)}元，成本价: {money(product.cost_price)}元\n"
            f"约束条件: {constraints_text}\n\n"
            "请按以下步骤操作：\n"
            "1. 从前面两个Agent的分析结果中提取各自的建议价格\n"
            "2. 计算候选价格 = (数据分析建议价 + 市场情报建议价) / 2\n"
            "3. 使用「评估风控规则」工具，传入以下JSON参数：\n"
            f'   {{"current_price": "{money(product.current_price)}", '
            f'"cost_price": "{money(product.cost_price)}", '
            '"candidate_price": "计算出的候选价格", '
            f'"constraints": {json.dumps(payload.constraints, ensure_ascii=False, default=_serialize_decimal)}}}\n'
            "4. 分析风控评估结果，判断候选价格是否安全\n"
            "5. 如果候选价格不通过，说明哪些约束被违反\n\n"
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
        context=[data_task, market_task],
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
            "执行策略判断：\n"
            "- 如果风控通过且预期利润高于基线利润 → 执行策略为「直接执行」\n"
            "- 如果风控通过但预期利润未超过基线 → 执行策略为「灰度发布」\n"
            "- 如果风控不通过 → 执行策略为「人工审核」\n\n"
            "请说明为什么采纳或不采纳每个专家的建议，给出清晰的决策理由。\n\n"
            "最终输出必须是严格的JSON格式："
        ),
        expected_output=(
            "严格JSON格式输出，字段如下：\n"
            '{"finalPrice": 最终建议价格(数字), '
            '"expectedSales": 预期月销量(整数), '
            '"expectedProfit": 预期月利润(数字), '
            '"profitGrowth": 利润变化额(数字,可为负), '
            '"executeStrategy": "直接执行/灰度发布/人工审核", '
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
