from dataclasses import dataclass

from app.agents.data_analysis_agent import DataAnalysisAgent
from app.agents.manager_agent import ManagerAgent
from app.agents.market_intel_agent import MarketIntelAgent
from app.agents.risk_control_agent import RiskControlAgent

try:
    from crewai import Agent as CrewAIAgent  # noqa: F401
    from crewai import Crew as CrewAICrew  # noqa: F401

    CREWAI_AVAILABLE = True
except Exception:
    CREWAI_AVAILABLE = False


@dataclass(slots=True)
class CrewBundle:
    data_agent: DataAnalysisAgent
    market_agent: MarketIntelAgent
    risk_agent: RiskControlAgent
    manager_agent: ManagerAgent
    crewai_available: bool


def build_crew_bundle() -> CrewBundle:
    return CrewBundle(
        data_agent=DataAnalysisAgent(),
        market_agent=MarketIntelAgent(),
        risk_agent=RiskControlAgent(),
        manager_agent=ManagerAgent(),
        crewai_available=CREWAI_AVAILABLE,
    )

