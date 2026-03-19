import json
import logging
from typing import Optional, Tuple

from app.schemas.decision import (
    AnalysisRequest,
    DataAnalysisResult,
    FinalDecision,
    MarketIntelResult,
    RiskControlResult,
)
from src.pricing_crew.orchestrator import pricing_crew_orchestrator

logger = logging.getLogger(__name__)


class DecisionService:
    def __init__(self):
        self._crewai_cache: dict[
            str,
            Tuple[DataAnalysisResult, MarketIntelResult, RiskControlResult, FinalDecision],
        ] = {}
        self._cache_limit = 32
        logger.info(
            "DecisionService initialized. crewai_enabled=%s",
            pricing_crew_orchestrator.is_available(),
        )

    def _cache_key(self, request: AnalysisRequest) -> str:
        return json.dumps(request.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)

    async def _run_full(
        self,
        request: AnalysisRequest,
    ) -> Tuple[DataAnalysisResult, MarketIntelResult, RiskControlResult, FinalDecision]:
        cache_key = self._cache_key(request)
        cached = self._crewai_cache.get(cache_key)
        if cached is not None:
            return cached

        result = await pricing_crew_orchestrator.run_full_workflow(request)
        self._crewai_cache[cache_key] = result
        if len(self._crewai_cache) > self._cache_limit:
            oldest_key = next(iter(self._crewai_cache))
            self._crewai_cache.pop(oldest_key, None)
        return result

    async def run_data_analysis(self, request: AnalysisRequest) -> DataAnalysisResult:
        logger.info("Running data analysis stage for product %s", request.product.product_id)
        data_result, _, _, _ = await self._run_full(request)
        return data_result

    async def run_market_intel(self, request: AnalysisRequest) -> MarketIntelResult:
        logger.info("Running market intel stage for product %s", request.product.product_id)
        _, market_result, _, _ = await self._run_full(request)
        return market_result

    async def run_risk_control(self, request: AnalysisRequest) -> RiskControlResult:
        logger.info("Running risk control stage for product %s", request.product.product_id)
        _, _, risk_result, _ = await self._run_full(request)
        return risk_result

    async def run_full_decision(
        self,
        request: AnalysisRequest,
    ) -> Tuple[DataAnalysisResult, MarketIntelResult, RiskControlResult, FinalDecision]:
        logger.info("Running full multi-agent decision flow for product %s", request.product.product_id)
        return await self._run_full(request)

    async def run_manager_decision(
        self,
        request: AnalysisRequest,
        data_result: Optional[DataAnalysisResult] = None,
        market_result: Optional[MarketIntelResult] = None,
        risk_result: Optional[RiskControlResult] = None,
    ) -> FinalDecision:
        logger.info("Running manager decision stage for product %s", request.product.product_id)

        if data_result is not None and market_result is not None and risk_result is not None:
            return await pricing_crew_orchestrator.run_manager_with_inputs(
                request=request,
                data_result=data_result,
                market_result=market_result,
                risk_result=risk_result,
            )

        _, _, _, final_result = await self.run_full_decision(request)
        return final_result


decision_service = DecisionService()
