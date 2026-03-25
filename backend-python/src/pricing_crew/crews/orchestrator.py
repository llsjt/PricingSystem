"""编排入口模块，统一调度四个智能体的执行顺序。"""

from __future__ import annotations

import asyncio
import logging
from typing import Tuple

from pricing_crew.core.agent_logic import (
    run_data_analysis_agent,
    run_manager_coordinator_agent,
    run_market_intel_agent,
    run_risk_control_agent,
)
from pricing_crew.core.schemas import AnalysisRequest, DataAnalysisResult, FinalDecision, MarketIntelResult, RiskControlResult
from pricing_crew.infrastructure.config.runtime import settings

logger = logging.getLogger(__name__)


class PricingCrewOrchestrator:
    """统一编排四个智能体，避免业务链路绕过同一调度入口。"""

    def __init__(self) -> None:
        self._crewai_enabled = bool(settings.crewai_enabled and settings.openai_api_key.strip())
        self._reason = ""
        if not self._crewai_enabled:
            self._reason = "当前使用本地确定性编排链路，未启用 CrewAI LLM 运行模式。"

    def is_available(self) -> bool:
        return True

    def unavailable_reason(self) -> str:
        return self._reason

    async def run_data_analysis(self, request: AnalysisRequest) -> DataAnalysisResult:
        """运行数据分析智能体。"""
        return await asyncio.to_thread(run_data_analysis_agent, request)

    async def run_market_intel(self, request: AnalysisRequest) -> MarketIntelResult:
        """运行市场情报智能体。"""
        return await asyncio.to_thread(run_market_intel_agent, request)

    async def run_risk_control(self, request: AnalysisRequest) -> RiskControlResult:
        """运行风险控制智能体。"""
        return await asyncio.to_thread(run_risk_control_agent, request)

    async def run_manager_with_inputs(
        self,
        request: AnalysisRequest,
        data_result: DataAnalysisResult,
        market_result: MarketIntelResult,
        risk_result: RiskControlResult,
    ) -> FinalDecision:
        """基于前三个智能体的结果运行决策经理。"""
        final_result = await asyncio.to_thread(
            run_manager_coordinator_agent,
            request,
            data_result,
            market_result,
            risk_result,
        )
        logger.info(
            "manager-only workflow finished. product=%s decision=%s",
            request.product.product_id,
            final_result.decision,
        )
        return final_result

    async def run_full_workflow(
        self,
        request: AnalysisRequest,
    ) -> Tuple[DataAnalysisResult, MarketIntelResult, RiskControlResult, FinalDecision]:
        """按统一顺序执行完整四智能体链路。"""
        data_result = await self.run_data_analysis(request)
        market_result = await self.run_market_intel(request)
        risk_result = await self.run_risk_control(request)
        final_result = await self.run_manager_with_inputs(request, data_result, market_result, risk_result)

        logger.info(
            "4-agent workflow finished. product=%s decision=%s suggested_price=%.2f crewai_enabled=%s",
            request.product.product_id,
            final_result.decision,
            final_result.suggested_price,
            self._crewai_enabled,
        )
        return data_result, market_result, risk_result, final_result


pricing_crew_orchestrator = PricingCrewOrchestrator()
