"""
CrewAI Crew 构建工厂
====================
根据定价任务的 Payload 动态生成 4 个 Task，
组装成一个顺序执行的 Crew，支持 Task 完成时的回调（用于实时写入卡片到数据库）。
"""

import json
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from crewai import Crew, Process, Task

from app.agents.crewai_agents import build_crewai_agents
from app.crew.protocols import CrewRunPayload
from app.utils.math_utils import money
from app.utils.text_utils import to_strategy_goal_cn


def _serialize_decimal(obj: Any) -> Any:
    """JSON 序列化时将 Decimal 转为 str"""
    if isinstance(obj, Decimal):
        return str(obj)
    return str(obj)


def _build_metrics_summary(payload: CrewRunPayload) -> str:
    """
    将近30天经营指标压缩为简洁的文本摘要，注入到 Task description 中，
    让 LLM 能直接看到关键数据而无需额外工具调用。
    """
    if not payload.metrics:
        return "暂无近30天经营数据"

    # 计算汇总指标
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


def build_pricing_crew(
    payload: CrewRunPayload,
    llm: object,
    on_task_done: Callable | None = None,
) -> Crew:
    """
    构建定价决策 Crew。

    参数:
        payload: 定价任务上下文（商品信息、指标、约束等）
        llm: CrewAI 兼容的 LLM 实例
        on_task_done: Task 完成时的回调函数（用于实时写入Agent卡片到DB）

    返回:
        配置好的 Crew 实例，调用 crew.kickoff() 即可执行
    """
    # ── 创建 4 个 Agent ────────────────────────────────────
    agents = build_crewai_agents(llm)

    # ── 准备注入到 Task description 的上下文数据 ───────────
    product = payload.product
    strategy_cn = to_strategy_goal_cn(payload.strategy_goal)
    metrics_summary = _build_metrics_summary(payload)
    constraints_text = _build_constraints_text(payload.constraints)

    # 将商品数据和指标序列化为 JSON，供 LLM 传递给工具调用
    product_dict = {
        "productId": product.product_id,
        "shopId": product.shop_id,
        "productName": product.product_name,
        "categoryName": product.category_name,
        "currentPrice": str(product.current_price),
        "costPrice": str(product.cost_price),
        "stock": product.stock,
    }
    metrics_list = [
        {
            "statDate": str(m.stat_date),
            "visitorCount": m.visitor_count,
            "addCartCount": m.add_cart_count,
            "payBuyerCount": m.pay_buyer_count,
            "salesCount": m.sales_count,
            "turnover": str(m.turnover),
            "conversionRate": str(m.conversion_rate),
        }
        for m in payload.metrics
    ]
    traffic_list = [
        {
            "statDate": str(t.stat_date),
            "trafficSource": t.traffic_source,
            "impressionCount": t.impression_count,
            "clickCount": t.click_count,
            "visitorCount": t.visitor_count,
            "payAmount": str(t.pay_amount),
            "roi": str(t.roi),
        }
        for t in payload.traffic
    ]

    # ── Task 1: 数据分析任务 ──────────────────────────────
    # 数据分析Agent基于经营数据评估价格弹性，输出建议价格和预期利润
    data_task = Task(
        description=(
            f"你正在为商品「{product.product_name}」制定定价策略。\n"
            f"当前售价: {money(product.current_price)}元，成本价: {money(product.cost_price)}元，"
            f"库存: {product.stock}件\n"
            f"策略目标: {strategy_cn}\n"
            f"基线月销量: {payload.baseline_sales}件，基线月利润: {money(payload.baseline_profit)}元\n"
            f"{metrics_summary}\n\n"
            "请按以下步骤操作：\n"
            "1. 使用「汇总商品经营数据」工具，传入以下JSON参数：\n"
            f'   {{"product": {json.dumps(product_dict, ensure_ascii=False)}, '
            f'"metrics": {json.dumps(metrics_list, ensure_ascii=False)}, '
            f'"traffic": {json.dumps(traffic_list, ensure_ascii=False)}}}\n'
            "2. 分析汇总结果，评估销售趋势（上升/下降/平稳）\n"
            "3. 根据策略目标确定建议价格：\n"
            "   - 利润优先：适当提价（建议在当前价基础上+1%~4%）\n"
            "   - 清仓促销：适当降价（建议降5%左右）\n"
            "   - 市场份额优先：小幅降价（建议降3%左右）\n"
            "4. 使用「预估调价后销量」工具计算预期销量\n"
            "5. 使用「预估利润」工具计算预期利润\n"
            "6. 确定建议价格区间（最低价不低于成本价×1.08）\n\n"
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
            '"summary": "分析摘要(中文字符串)"}'
        ),
        agent=agents["DATA_ANALYSIS"],
        callback=on_task_done,
    )

    # ── Task 2: 市场情报任务 ──────────────────────────────
    # 市场情报Agent基于竞品数据分析市场价格带，输出市场建议价格
    market_task = Task(
        description=(
            f"你正在为商品「{product.product_name}」分析市场竞争态势。\n"
            f"品类: {product.category_name or '通用品类'}，当前售价: {money(product.current_price)}元\n"
            f"策略目标: {strategy_cn}\n\n"
            "请按以下步骤操作：\n"
            "1. 使用「查询竞品价格数据」工具，传入以下JSON参数：\n"
            f'   {{"product_id": {product.product_id}, '
            f'"product_title": "{product.product_name}", '
            f'"category_name": "{product.category_name or "通用品类"}", '
            f'"current_price": "{money(product.current_price)}"}}\n'
            "2. 分析竞品数据：识别价格地板（最低价）、天花板（最高价）和均价\n"
            "3. 评估促销压力和竞争强度\n"
            "4. 根据策略目标给出市场建议价格：\n"
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
            '"summary": "市场分析摘要(中文字符串)", '
            '"simulatedSamples": 竞品样本数(整数)}'
        ),
        agent=agents["MARKET_INTEL"],
        context=[data_task],
        callback=on_task_done,
    )

    # ── Task 3: 风险控制任务 ──────────────────────────────
    # 风控Agent对候选价格执行硬约束校验，确保定价安全
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
            '"summary": "风控评估摘要(中文字符串)"}'
        ),
        agent=agents["RISK_CONTROL"],
        context=[data_task, market_task],
        callback=on_task_done,
    )

    # ── Task 4: 经理协调任务 ──────────────────────────────
    # 经理Agent综合三个专家意见，输出最终可执行的定价决策
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
        process=Process.sequential,  # 4个任务按顺序串行执行
        verbose=True,
    )

    return crew
