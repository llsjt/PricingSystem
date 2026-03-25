"""CrewAI 编排定义模块，声明四个 Agent 与工具绑定关系。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from pydantic import BaseModel

from pricing_crew.crews.models import (
    CrewDataAnalysisOutput,
    CrewManagerDecisionOutput,
    CrewMarketIntelOutput,
    CrewRiskControlOutput,
)
from pricing_crew.infrastructure.tools.custom_tool import (
    DatabaseProductContextTool,
    DatabaseRiskContextTool,
    MarketSnapshotTool,
    RiskConstraintTool,
    SalesMetricsTool,
    TaobaoCompetitorFetchTool,
)


@CrewBase
class PricingDecisionCrew:
    """CrewAI 风格的四智能体定价决策编排类。"""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    llm: Any = None
    verbose: bool = False
    use_structured_output: bool = True

    def _build_task(
        self,
        task_key: str,
        output_model: Type[BaseModel],
        owner: Agent,
        context: Optional[List[Task]] = None,
    ) -> Task:
        kwargs: Dict[str, Any] = {
            "config": self.tasks_config[task_key],
            "agent": owner,
        }
        if context:
            kwargs["context"] = context
        if self.use_structured_output:
            kwargs["output_pydantic"] = output_model
        return Task(**kwargs)

    @agent
    def data_analysis_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["data_analysis_agent"],
            llm=self.llm,
            tools=[DatabaseProductContextTool(), SalesMetricsTool()],
            allow_delegation=False,
            verbose=self.verbose,
        )

    @agent
    def market_intel_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["market_intel_agent"],
            llm=self.llm,
            tools=[TaobaoCompetitorFetchTool(), MarketSnapshotTool()],
            allow_delegation=False,
            verbose=self.verbose,
        )

    @agent
    def risk_control_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["risk_control_agent"],
            llm=self.llm,
            tools=[DatabaseRiskContextTool(), RiskConstraintTool()],
            allow_delegation=False,
            verbose=self.verbose,
        )

    @agent
    def decision_manager_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["decision_manager_agent"],
            llm=self.llm,
            allow_delegation=False,
            verbose=self.verbose,
        )

    @task
    def data_analysis_task(self) -> Task:
        return self._build_task(
            task_key="data_analysis_task",
            output_model=CrewDataAnalysisOutput,
            owner=self.data_analysis_agent(),
        )

    @task
    def market_intel_task(self) -> Task:
        return self._build_task(
            task_key="market_intel_task",
            output_model=CrewMarketIntelOutput,
            owner=self.market_intel_agent(),
            context=[self.data_analysis_task()],
        )

    @task
    def risk_control_task(self) -> Task:
        return self._build_task(
            task_key="risk_control_task",
            output_model=CrewRiskControlOutput,
            owner=self.risk_control_agent(),
            context=[self.data_analysis_task(), self.market_intel_task()],
        )

    @task
    def manager_decision_task(self) -> Task:
        return self._build_task(
            task_key="manager_decision_task",
            output_model=CrewManagerDecisionOutput,
            owner=self.decision_manager_agent(),
            context=[self.data_analysis_task(), self.market_intel_task(), self.risk_control_task()],
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[
                self.data_analysis_agent(),
                self.market_intel_agent(),
                self.risk_control_agent(),
                self.decision_manager_agent(),
            ],
            tasks=[
                self.data_analysis_task(),
                self.market_intel_task(),
                self.risk_control_task(),
                self.manager_decision_task(),
            ],
            process=Process.sequential,
            verbose=self.verbose,
        )
