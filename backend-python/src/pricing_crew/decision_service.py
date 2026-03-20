"""决策服务模块，封装四智能体执行入口与结果缓存。"""

from __future__ import annotations

import json
from typing import Optional, Tuple

from pricing_crew.orchestrator import pricing_crew_orchestrator
from pricing_crew.schemas import AnalysisRequest, DataAnalysisResult, FinalDecision, MarketIntelResult, RiskControlResult


class DecisionService:
    def __init__(self) -> None:
        self._cache: dict[str, Tuple[DataAnalysisResult, MarketIntelResult, RiskControlResult, FinalDecision]] = {}
        self._cache_limit = 64

    def _cache_key(self, request: AnalysisRequest) -> str:
        return json.dumps(request.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)

    async def _run_full(self, request: AnalysisRequest):
        if request.business_context.get("prefer_db_tools"):
            return await pricing_crew_orchestrator.run_full_workflow(request)
        key = self._cache_key(request)
        if key in self._cache:
            return self._cache[key]
        result = await pricing_crew_orchestrator.run_full_workflow(request)
        self._cache[key] = result
        if len(self._cache) > self._cache_limit:
            oldest_key = next(iter(self._cache))
            self._cache.pop(oldest_key, None)
        return result

    async def run_data_analysis(self, request: AnalysisRequest) -> DataAnalysisResult:
        data_result, _, _, _ = await self._run_full(request)
        return data_result

    async def run_market_intel(self, request: AnalysisRequest) -> MarketIntelResult:
        _, market_result, _, _ = await self._run_full(request)
        return market_result

    async def run_risk_control(self, request: AnalysisRequest) -> RiskControlResult:
        _, _, risk_result, _ = await self._run_full(request)
        return risk_result

    async def run_full_decision(self, request: AnalysisRequest):
        return await self._run_full(request)

    async def run_manager_decision(
        self,
        request: AnalysisRequest,
        data_result: Optional[DataAnalysisResult] = None,
        market_result: Optional[MarketIntelResult] = None,
        risk_result: Optional[RiskControlResult] = None,
    ) -> FinalDecision:
        if data_result and market_result and risk_result:
            return await pricing_crew_orchestrator.run_manager_with_inputs(request, data_result, market_result, risk_result)
        _, _, _, final = await self._run_full(request)
        return final


decision_service = DecisionService()
