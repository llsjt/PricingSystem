import logging
from typing import Optional

from app.agents.data_analysis_agent import DataAnalysisAgent
from app.agents.manager_coordinator_agent import ManagerCoordinatorAgent
from app.agents.market_intel_agent import MarketIntelAgent
from app.agents.risk_control_agent import RiskControlAgent
from app.schemas.decision import (
    AnalysisRequest,
    DataAnalysisResult,
    FinalDecision,
    MarketIntelResult,
    RiskControlResult,
)

logger = logging.getLogger(__name__)


class DecisionService:
    def __init__(self):
        self.data_analyst = DataAnalysisAgent()
        self.market_intel = MarketIntelAgent()
        self.risk_control = RiskControlAgent()
        self.manager = ManagerCoordinatorAgent()
        logger.info("DecisionService initialized")

    async def run_data_analysis(self, request: AnalysisRequest) -> DataAnalysisResult:
        logger.info("Running DataAnalysisAgent for product %s", request.product.product_id)
        return self.data_analyst.analyze(request)

    async def run_market_intel(self, request: AnalysisRequest) -> MarketIntelResult:
        logger.info("Running MarketIntelAgent for product %s", request.product.product_id)
        return self.market_intel.analyze(request)

    async def run_risk_control(self, request: AnalysisRequest) -> RiskControlResult:
        logger.info("Running RiskControlAgent for product %s", request.product.product_id)
        return self.risk_control.analyze(request)

    async def run_manager_decision(
        self,
        request: AnalysisRequest,
        data_result: Optional[DataAnalysisResult] = None,
        market_result: Optional[MarketIntelResult] = None,
        risk_result: Optional[RiskControlResult] = None,
    ) -> FinalDecision:
        logger.info("Running ManagerCoordinatorAgent for product %s", request.product.product_id)

        if data_result is None:
            data_result = await self.run_data_analysis(request)
        if market_result is None:
            market_result = await self.run_market_intel(request)
        if risk_result is None:
            risk_result = await self.run_risk_control(request)

        return self.manager.coordinate(
            request=request,
            data_result=data_result,
            market_result=market_result,
            risk_result=risk_result,
        )


decision_service = DecisionService()
