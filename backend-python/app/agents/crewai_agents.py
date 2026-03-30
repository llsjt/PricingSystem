"""
CrewAI Agent 定义
=================
使用 CrewAI 框架定义 4 个真正由 LLM 驱动的 Agent，
每个 Agent 拥有明确的中文角色、目标、背景故事和专属工具集。
"""

from crewai import Agent

from app.core.config import get_settings
from app.tools.crewai_tools import (
    clean_outliers,
    estimate_profit,
    estimate_sales_volume,
    evaluate_risk_rules,
    search_competitors,
    summarize_product_data,
)


def build_crewai_agents(llm: object) -> dict[str, Agent]:
    """
    构建 4 个 CrewAI Agent 实例。

    参数:
        llm: CrewAI 兼容的 LLM 实例（OpenAICompatibleCrewAILLM）

    返回:
        字典 {"DATA_ANALYSIS": Agent, "MARKET_INTEL": Agent,
              "RISK_CONTROL": Agent, "MANAGER_COORDINATOR": Agent}
    """
    settings = get_settings()

    # ── 各 Agent 共享的运行约束参数 ────────────────────────────
    common_kwargs = {
        "llm": llm,
        "verbose": True,
        "max_iter": max(settings.crewai_agent_max_iter, 2),
        "max_execution_time": max(settings.crewai_agent_max_execution_seconds, 15),
        "max_retry_limit": settings.crewai_agent_max_retry_limit,
        "allow_delegation": False,  # 默认不允许委托，经理Agent除外
    }

    # ── 1. 数据分析 Agent ─────────────────────────────────────
    # 负责分析商品近30天销售数据，评估价格弹性，给出数据驱动的建议价格
    data_analysis_agent = Agent(
        role="数据分析专家",
        goal=(
            "基于商品近30天经营数据（销量、流量、转化率、库存），"
            "评估价格弹性与利润-销量关系，给出数据驱动的建议价格和价格区间。"
            "你必须使用工具获取数据并计算，不允许凭空编造数字。"
        ),
        backstory=(
            "你是一位资深电商数据分析师，拥有多年电商定价经验。"
            "你擅长通过历史销售数据、流量趋势和转化率来评估价格调整对销量和利润的影响。"
            "你的每一个数字结论都必须来自工具的计算结果，绝不凭空猜测。"
        ),
        tools=[summarize_product_data, clean_outliers, estimate_sales_volume, estimate_profit],
        **common_kwargs,
    )

    # ── 2. 市场情报 Agent ─────────────────────────────────────
    # 负责获取竞品价格数据，识别市场价格带，给出市场可接受的建议价格
    market_intel_agent = Agent(
        role="市场情报分析师",
        goal=(
            "基于竞品价格数据（模拟数据），识别市场价格带和竞争态势，"
            "给出市场可接受的建议价格。"
            "你必须使用竞品查询工具获取数据，而非自行编造竞品信息。"
        ),
        backstory=(
            "你是一位市场情报分析师，专注于电商竞品价格监控。"
            "你通过分析竞品在各平台（淘宝、天猫、京东、拼多多、抖音）的定价、"
            "促销力度和销量趋势来判断市场合理价格区间。"
            "你的分析结论必须基于竞品数据工具返回的真实样本。"
        ),
        tools=[search_competitors],
        **common_kwargs,
    )

    # ── 3. 风险控制 Agent ─────────────────────────────────────
    # 负责对候选价格执行硬约束校验，确保定价不会亏损或违反业务规则
    risk_control_agent = Agent(
        role="风险控制专家",
        goal=(
            "对候选价格执行硬约束校验：成本底线、最低利润率（默认15%）、"
            "价格上下限、最大折扣率，判断价格是否安全可执行。"
            "你必须使用风控规则评估工具进行校验，绝不允许跳过硬约束检查。"
        ),
        backstory=(
            "你是一位严格的风控专家，负责为电商定价决策把关。"
            "你的核心职责是确保任何定价建议都不会导致亏损或违反业务约束。"
            "你宁可保守也不放过任何风险，任何不满足硬约束的价格都必须被标记为需人工复核。"
        ),
        tools=[evaluate_risk_rules, estimate_profit],
        **common_kwargs,
    )

    # ── 4. 经理协调 Agent ─────────────────────────────────────
    # 负责综合前三个 Agent 的意见，输出最终可执行的定价决策
    manager_agent = Agent(
        role="定价决策经理",
        goal=(
            "综合数据分析、市场情报和风险控制三个专家的意见，"
            "权衡利润最优、市场竞争力和风控安全性，"
            "输出最终可执行的定价决策，包括最终价格、预期销量、预期利润和执行策略。"
        ),
        backstory=(
            "你是定价决策的最终负责人，也是一位经验丰富的电商运营总监。"
            "你需要在利润、市场份额和风险之间找到最佳平衡点。"
            "你的决策必须参考前三个专家的分析结果，并给出清晰的理由说明"
            "为什么采纳或不采纳某个专家的建议。"
            "执行策略必须是以下之一：直接执行、灰度发布、人工审核。"
        ),
        tools=[estimate_sales_volume, estimate_profit],
        **common_kwargs,
    )

    return {
        "DATA_ANALYSIS": data_analysis_agent,
        "MARKET_INTEL": market_intel_agent,
        "RISK_CONTROL": risk_control_agent,
        "MANAGER_COORDINATOR": manager_agent,
    }
