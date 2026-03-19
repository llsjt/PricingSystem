from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from pydantic import BaseModel

from .models import (
    CrewDataAnalysisOutput,
    CrewManagerDecisionOutput,
    CrewMarketIntelOutput,
    CrewRiskControlOutput,
)
from .tools.custom_tool import MarketSnapshotTool, RiskConstraintTool, SalesMetricsTool


@CrewBase
class PricingDecisionCrew:
    """CrewAI-style 4-agent pricing decision crew."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    llm: Any = None
    verbose: bool = False
    use_structured_output: bool = True

    def configure(self, llm: Any, *, verbose: bool = False, use_structured_output: bool = True) -> "PricingDecisionCrew":
        self.llm = llm
        self.verbose = verbose
        self.use_structured_output = use_structured_output
        return self

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
            tools=[SalesMetricsTool()],
            allow_delegation=False,
            verbose=self.verbose,
        )

    @agent
    def market_intel_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["market_intel_agent"],
            llm=self.llm,
            tools=[MarketSnapshotTool()],
            allow_delegation=False,
            verbose=self.verbose,
        )

    @agent
    def risk_control_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["risk_control_agent"],
            llm=self.llm,
            tools=[RiskConstraintTool()],
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

    def build_manager_only_task(self) -> Task:
        return self._build_task(
            task_key="manager_only_task",
            output_model=CrewManagerDecisionOutput,
            owner=self.decision_manager_agent(),
        )

    def build_manager_only_crew(self) -> Crew:
        manager_task = self.build_manager_only_task()
        manager_agent = self.decision_manager_agent()
        return Crew(
            agents=[manager_agent],
            tasks=[manager_task],
            process=Process.sequential,
            verbose=self.verbose,
        )

    @crew
    def crew(self) -> Crew:
        """Create full 4-agent sequential crew."""
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
