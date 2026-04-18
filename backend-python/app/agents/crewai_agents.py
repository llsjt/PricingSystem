"""
CrewAI agent definitions.
"""

from crewai import Agent

from app.core.config import get_settings
from app.tools.crewai_tools import estimate_profit, estimate_sales_volume, evaluate_risk_rules


def build_crewai_agents(*, analysis_llm: object, manager_llm: object) -> dict[str, Agent]:
    settings = get_settings()

    analysis_kwargs = {
        "llm": analysis_llm,
        "verbose": True,
        "max_iter": max(settings.analysis_agent_max_iter, 2),
        "max_execution_time": max(settings.analysis_agent_max_execution_seconds, 15),
        "max_retry_limit": settings.crewai_agent_max_retry_limit,
        "allow_delegation": False,
    }
    manager_kwargs = {
        "llm": manager_llm,
        "verbose": True,
        "max_iter": max(settings.manager_agent_max_iter, 2),
        "max_execution_time": max(settings.manager_agent_max_execution_seconds, 15),
        "max_retry_limit": settings.crewai_agent_max_retry_limit,
        "allow_delegation": False,
    }

    data_analysis_agent = Agent(
        role="数据分析专家",
        goal=(
            "基于商品近30天经营数据评估价格弹性与利润-销量关系，"
            "给出数据驱动的建议价格和价格区间。"
            "必须用工具计算销量和利润，不允许凭空编造数字。"
        ),
        backstory=(
            "你是一位资深电商数据分析师，擅长根据经营指标估算调价后的销量和利润。"
            "你的结论必须可追溯到工具计算结果。"
        ),
        tools=[estimate_sales_volume, estimate_profit],
        **analysis_kwargs,
    )

    market_intel_agent = Agent(
        role="市场情报分析师",
        goal="基于预先整理好的竞品摘要识别市场价格带和竞争态势，给出市场可接受的建议价格。",
        backstory="你是一位市场情报分析师，擅长从竞品分布、促销力度和平台差异中判断市场价格带。",
        tools=[],
        **analysis_kwargs,
    )

    risk_control_agent = Agent(
        role="风险控制专家",
        goal="对候选价格执行硬约束校验，包括成本底线、最低利润率、价格上下限和最大折扣率，判断价格是否安全可执行。",
        backstory="你是一位严格的风控专家，职责是阻止亏损、超限折扣或违反业务规则的定价。",
        tools=[evaluate_risk_rules, estimate_profit],
        **analysis_kwargs,
    )

    manager_agent = Agent(
        role="定价决策经理",
        goal=(
            "综合数据分析、市场情报和风险控制三方意见，输出最终可执行的定价决策，"
            "包括最终价格、预期销量、预期利润和执行策略。"
        ),
        backstory=(
            "你是定价决策的最终负责人，需要在利润、竞争力和风险之间找到平衡，"
            "并清晰说明采纳或否决各专家建议的原因。"
        ),
        tools=[estimate_sales_volume, estimate_profit],
        **manager_kwargs,
    )

    return {
        "DATA_ANALYSIS": data_analysis_agent,
        "MARKET_INTEL": market_intel_agent,
        "RISK_CONTROL": risk_control_agent,
        "MANAGER_COORDINATOR": manager_agent,
    }
