from decimal import Decimal
import os
from typing import Any

# 禁用 CrewAI 远端遥测，避免本地离线演示时出现 30s+ 超时。
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

from crewai import Agent, Crew, Process, Task
from crewai.llms.base_llm import BaseLLM

from app.crew.protocols import CrewRunPayload
from app.utils.math_utils import money


class MockCrewAILLM(BaseLLM):
    """离线可运行的 CrewAI 模拟 LLM，避免依赖外部模型服务。"""

    def __init__(self) -> None:
        super().__init__(model="mock-crewai-llm", provider="custom")

    def call(
        self,
        messages: str | list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        callbacks: list[Any] | None = None,
        available_functions: dict[str, Any] | None = None,
        from_task: Task | None = None,
        from_agent: Agent | None = None,
        response_model: type | None = None,
    ) -> str | Any:
        role = from_agent.role if from_agent is not None else "Agent"
        return f"{role} 已完成阶段协作分析（MockCrewAILLM）。"


def run_crewai_session(payload: CrewRunPayload) -> dict[str, Any]:
    """启动 4 Agent CrewAI 协作过程，返回可记录的执行摘要。"""
    llm = MockCrewAILLM()

    data_agent = Agent(
        role="数据分析Agent",
        goal="分析商品数据趋势并给出价格建议",
        backstory="擅长销量、转化率和利润弹性分析。",
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )
    market_agent = Agent(
        role="市场情报Agent",
        goal="基于竞品样本判断市场价格带",
        backstory="擅长比较同类商品的市场价格水平。",
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )
    risk_agent = Agent(
        role="风控Agent",
        goal="校验利润率和价格上下限约束",
        backstory="擅长识别价格决策中的经营风险。",
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )
    manager_agent = Agent(
        role="经理协调Agent",
        goal="综合三方意见输出最终决策",
        backstory="负责多 Agent 结果整合和冲突裁决。",
        llm=llm,
        verbose=False,
        allow_delegation=True,
    )

    product = payload.product
    base_context = (
        f"商品={product.product_name}; 当前价={money(product.current_price)}; "
        f"成本={money(product.cost_price)}; 库存={product.stock}; 策略={payload.strategy_goal}; "
        f"约束={payload.constraints}"
    )

    data_task = Task(
        description=f"请完成数据分析并给出建议价格区间。上下文：{base_context}",
        expected_output="包含价格区间、预估销量、预估利润、置信度的中文摘要。",
        agent=data_agent,
    )
    market_task = Task(
        description=f"请完成市场价带分析并给出建议价格。上下文：{base_context}",
        expected_output="包含市场底价、市场上限、建议价、样本规模的中文摘要。",
        agent=market_agent,
        context=[data_task],
    )
    risk_task = Task(
        description=f"请评估候选价格风险并给出风控建议。上下文：{base_context}",
        expected_output="包含是否通过、风险等级、安全底价、是否人工复核的中文摘要。",
        agent=risk_agent,
        context=[data_task, market_task],
    )
    manager_task = Task(
        description="请综合数据、市场、风控三方意见，给出最终定价建议与执行策略。",
        expected_output="包含最终价格、执行策略、结论摘要。",
        agent=manager_agent,
        context=[data_task, market_task, risk_task],
    )

    crew = Crew(
        name="pricing-multi-agent-crew",
        agents=[data_agent, market_agent, risk_agent],
        manager_agent=manager_agent,
        tasks=[data_task, market_task, risk_task, manager_task],
        process=Process.hierarchical,
        verbose=False,
    )
    output = crew.kickoff(
        inputs={
            "task_id": payload.task_id,
            "product_id": product.product_id,
            "strategy_goal": payload.strategy_goal,
            "baseline_sales": payload.baseline_sales,
            "baseline_profit": str(payload.baseline_profit),
        }
    )

    return {
        "enabled": True,
        "process": "hierarchical",
        "taskCount": 4,
        "agentRoles": [data_agent.role, market_agent.role, risk_agent.role, manager_agent.role],
        "crewOutput": str(output),
    }
