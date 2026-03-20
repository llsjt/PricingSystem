"""编排入口模块，组织四智能体本地执行流程。"""

from __future__ import annotations

import logging
from typing import Tuple

from pricing_crew.agent_logic import (
    run_data_analysis_agent,
    run_manager_coordinator_agent,
    run_market_intel_agent,
    run_risk_control_agent,
)
from pricing_crew.config.runtime import settings
from pricing_crew.schemas import AnalysisRequest, DataAnalysisResult, FinalDecision, MarketIntelResult, RiskControlResult

logger = logging.getLogger(__name__)


class PricingCrewOrchestrator:
    """四智能体编排入口，统一调度本地规则执行链路。"""

    def __init__(self) -> None:
        self._crewai_enabled = bool(settings.crewai_enabled and settings.openai_api_key.strip())
        self._reason = ""
        if not self._crewai_enabled:
            self._reason = "已启用本地确定性模式（CREWAI LLM 模式关闭）。"

    def is_available(self) -> bool:
        return True

    def unavailable_reason(self) -> str:
        return self._reason

    async def run_full_workflow(
        self,
        request: AnalysisRequest,
    ) -> Tuple[DataAnalysisResult, MarketIntelResult, RiskControlResult, FinalDecision]:
        data_result = run_data_analysis_agent(request)
        market_result = run_market_intel_agent(request)
        risk_result = run_risk_control_agent(request)
        final_result = run_manager_coordinator_agent(request, data_result, market_result, risk_result)

        logger.info(
            "4-agent workflow finished. product=%s decision=%s suggested_price=%.2f",
            request.product.product_id,
            final_result.decision,
            final_result.suggested_price,
        )
        return data_result, market_result, risk_result, final_result

    async def run_manager_with_inputs(
        self,
        request: AnalysisRequest,
        data_result: DataAnalysisResult,
        market_result: MarketIntelResult,
        risk_result: RiskControlResult,
    ) -> FinalDecision:
        final_result = run_manager_coordinator_agent(request, data_result, market_result, risk_result)
        logger.info(
            "manager-only workflow finished. product=%s decision=%s",
            request.product.product_id,
            final_result.decision,
        )
        return final_result


pricing_crew_orchestrator = PricingCrewOrchestrator()
