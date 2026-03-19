from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar

from pydantic import BaseModel

from app.core.config import settings
from app.orchestration.crewai_models import (
    CrewDataAnalysisOutput,
    CrewManagerDecisionOutput,
    CrewMarketIntelOutput,
    CrewRiskControlOutput,
)
from app.schemas.decision import (
    AgentSummary,
    AnalysisRequest,
    DataAnalysisResult,
    ExecutionPlan,
    ExpectedOutcomes,
    FinalDecision,
    MarketIntelResult,
    RiskControlResult,
)

logger = logging.getLogger(__name__)
TModel = TypeVar("TModel", bound=BaseModel)


class CrewAIOrchestrator:
    """
    CrewAI orchestration entrypoint.

    The flow follows the official CrewAI sequential model:
    1) Define Agents
    2) Define Tasks (with context dependencies)
    3) Build Crew(process=Process.sequential)
    4) kickoff / kickoff_async with explicit inputs
    """

    def __init__(self) -> None:
        self.enabled = bool(settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip())
        self._reason = ""
        self.llm = None
        if not self.enabled:
            self._reason = "OPENAI_API_KEY is empty."
            return

        try:
            from crewai import LLM

            model_name = self._normalize_model(settings.OPENAI_MODEL_NAME)
            # CrewAI/LiteLLM may read OpenAI-compatible credentials from env vars internally.
            # Keep explicit kwargs and provide env fallbacks for provider adapters.
            if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip():
                os.environ.setdefault("OPENAI_API_KEY", settings.OPENAI_API_KEY)
            if settings.OPENAI_API_BASE and settings.OPENAI_API_BASE.strip():
                os.environ.setdefault("OPENAI_API_BASE", settings.OPENAI_API_BASE)
                os.environ.setdefault("OPENAI_BASE_URL", settings.OPENAI_API_BASE)

            llm_kwargs: Dict[str, Any] = {
                "model": model_name,
                "api_key": settings.OPENAI_API_KEY,
                "temperature": 0.2,
            }
            if settings.OPENAI_API_BASE and settings.OPENAI_API_BASE.strip():
                llm_kwargs["base_url"] = settings.OPENAI_API_BASE
            self.llm = LLM(**llm_kwargs)
            logger.info("CrewAI LLM initialized with model=%s", model_name)
        except Exception as exc:
            self.enabled = False
            self._reason = f"CrewAI init failed: {exc}"
            logger.exception("Failed to initialize CrewAI")

    def is_available(self) -> bool:
        return self.enabled and self.llm is not None

    def unavailable_reason(self) -> str:
        return self._reason or "CrewAI unavailable"

    async def run_full_workflow(
        self, request: AnalysisRequest
    ) -> Tuple[DataAnalysisResult, MarketIntelResult, RiskControlResult, FinalDecision]:
        """
        Execute full 4-agent workflow through CrewAI.
        """
        self._ensure()
        from crewai import Agent, Crew, Process, Task

        payload = self._payload(request)
        request_json = self._dump_json(payload)

        data_agent = Agent(
            role="Data Analysis Specialist",
            goal="Analyze sales and inventory, then provide a constrained pricing-direction recommendation.",
            backstory=(
                "You are rigorous about trend evidence, demand elasticity and inventory pressure. "
                "Your output must be structured and auditable."
            ),
            llm=self.llm,
            allow_delegation=False,
            verbose=False,
        )

        market_agent = Agent(
            role="Market Intelligence Specialist",
            goal="Assess competitive pressure and market positioning to support pricing direction.",
            backstory=(
                "You focus on competitor price structure, market signals and realistic market tactics. "
                "You avoid unsupported claims."
            ),
            llm=self.llm,
            allow_delegation=False,
            verbose=False,
        )

        risk_agent = Agent(
            role="Risk Control Specialist",
            goal="Enforce profitability, compliance and hard pricing constraints.",
            backstory=(
                "You are the strict veto gate. Any recommendation violating margin or floor constraints "
                "must be rejected."
            ),
            llm=self.llm,
            allow_delegation=False,
            verbose=False,
        )

        manager_agent = Agent(
            role="Decision Manager",
            goal="Integrate all specialist outputs and produce one executable final pricing decision.",
            backstory=(
                "You resolve conflicts among specialists and issue the final decision with reasons, "
                "risk warnings and contingency plan."
            ),
            llm=self.llm,
            allow_delegation=False,
            verbose=False,
        )

        output = None
        last_exc: Optional[Exception] = None
        for structured in (True, False):
            try:
                data_task = self._make_task(
                    task_cls=Task,
                    description=self._data_prompt(),
                    expected_output="Strict JSON matching the DataAnalysis output schema.",
                    output_model=CrewDataAnalysisOutput,
                    agent=data_agent,
                    structured=structured,
                )
                market_task = self._make_task(
                    task_cls=Task,
                    description=self._market_prompt(),
                    expected_output="Strict JSON matching the MarketIntel output schema.",
                    output_model=CrewMarketIntelOutput,
                    agent=market_agent,
                    context=[data_task],
                    structured=structured,
                )
                risk_task = self._make_task(
                    task_cls=Task,
                    description=self._risk_prompt(),
                    expected_output="Strict JSON matching the RiskControl output schema.",
                    output_model=CrewRiskControlOutput,
                    agent=risk_agent,
                    context=[data_task, market_task],
                    structured=structured,
                )
                manager_task = self._make_task(
                    task_cls=Task,
                    description=self._manager_prompt(),
                    expected_output="Strict JSON matching the Final Manager output schema.",
                    output_model=CrewManagerDecisionOutput,
                    agent=manager_agent,
                    context=[data_task, market_task, risk_task],
                    structured=structured,
                )

                crew = Crew(
                    agents=[data_agent, market_agent, risk_agent, manager_agent],
                    tasks=[data_task, market_task, risk_task, manager_task],
                    process=Process.sequential,
                    verbose=False,
                )
                output = await self._kickoff(crew, inputs={"request_json": request_json})
                break
            except Exception as exc:
                last_exc = exc
                if structured and self._is_structured_output_unsupported(exc):
                    logger.warning(
                        "Structured Task output is not supported by current model/provider. "
                        "Retrying CrewAI workflow with raw JSON output parsing. error=%s",
                        exc,
                    )
                    continue
                raise

        if output is None:
            if last_exc is not None:
                raise last_exc
            raise RuntimeError("CrewAI workflow failed without explicit exception.")

        data_draft = self._extract(output, 0, CrewDataAnalysisOutput)
        market_draft = self._extract(output, 1, CrewMarketIntelOutput)
        risk_draft = self._extract(output, 2, CrewRiskControlOutput)
        manager_draft = self._extract(output, 3, CrewManagerDecisionOutput)

        data_result = self._to_data_result(request, data_draft)
        market_result = self._to_market_result(market_draft)
        risk_result = self._to_risk_result(request, risk_draft)
        final_result = self._to_final_result(request, manager_draft, data_result, market_result, risk_result)
        return data_result, market_result, risk_result, final_result

    async def run_manager_with_inputs(
        self,
        request: AnalysisRequest,
        data_result: DataAnalysisResult,
        market_result: MarketIntelResult,
        risk_result: RiskControlResult,
    ) -> FinalDecision:
        """
        Execute manager-only orchestration when upstream results already exist.
        """
        self._ensure()
        from crewai import Agent, Crew, Process, Task

        manager_agent = Agent(
            role="Decision Manager",
            goal="Synthesize specialist outputs into one final and executable decision.",
            backstory="You are accountable for conflict resolution and final actionability.",
            llm=self.llm,
            allow_delegation=False,
            verbose=False,
        )
        payload = {
            "request": self._payload(request),
            "data_result": data_result.model_dump(mode="json"),
            "market_result": market_result.model_dump(mode="json"),
            "risk_result": risk_result.model_dump(mode="json"),
        }
        output = None
        last_exc: Optional[Exception] = None
        for structured in (True, False):
            try:
                manager_task = self._make_task(
                    task_cls=Task,
                    description=self._manager_only_prompt(),
                    expected_output="Strict JSON matching the Final Manager output schema.",
                    output_model=CrewManagerDecisionOutput,
                    agent=manager_agent,
                    structured=structured,
                )
                crew = Crew(
                    agents=[manager_agent],
                    tasks=[manager_task],
                    process=Process.sequential,
                    verbose=False,
                )
                output = await self._kickoff(crew, inputs={"manager_input_json": self._dump_json(payload)})
                break
            except Exception as exc:
                last_exc = exc
                if structured and self._is_structured_output_unsupported(exc):
                    logger.warning(
                        "Structured manager output is not supported by current model/provider. "
                        "Retrying with raw JSON output parsing. error=%s",
                        exc,
                    )
                    continue
                raise

        if output is None:
            if last_exc is not None:
                raise last_exc
            raise RuntimeError("CrewAI manager-only workflow failed without explicit exception.")
        manager_draft = self._extract(output, 0, CrewManagerDecisionOutput)
        return self._to_final_result(request, manager_draft, data_result, market_result, risk_result)

    def _make_task(
        self,
        task_cls: Any,
        description: str,
        expected_output: str,
        output_model: Type[BaseModel],
        agent: Any,
        structured: bool,
        context: Optional[List[Any]] = None,
    ) -> Any:
        kwargs: Dict[str, Any] = {
            "description": description,
            "expected_output": expected_output,
            "agent": agent,
        }
        if context:
            kwargs["context"] = context
        if structured:
            kwargs["output_pydantic"] = output_model
        return task_cls(**kwargs)

    def _is_structured_output_unsupported(self, exc: Exception) -> bool:
        text = str(exc).lower()
        markers = [
            "tool_choice",
            "thinking mode",
            "response_format",
            "json_schema",
            "output_pydantic",
        ]
        return any(marker in text for marker in markers)

    async def _kickoff(self, crew: Any, inputs: Optional[Dict[str, Any]] = None) -> Any:
        """
        CrewAI kickoff wrapper.
        Official docs recommend kickoff_async(inputs=...) and kickoff(inputs=...).
        """
        kickoff_inputs = inputs or {}

        kickoff_async = getattr(crew, "kickoff_async", None)
        if callable(kickoff_async):
            return await kickoff_async(inputs=kickoff_inputs)

        akickoff = getattr(crew, "akickoff", None)
        if callable(akickoff):
            return await akickoff(inputs=kickoff_inputs)

        kickoff = getattr(crew, "kickoff", None)
        if callable(kickoff):
            return await asyncio.to_thread(kickoff, inputs=kickoff_inputs)

        raise RuntimeError("Crew object does not expose kickoff methods")

    def _extract(self, output: Any, idx: int, model: Type[TModel]) -> TModel:
        """
        Convert Crew output into a pydantic model robustly.
        """
        tasks_output = getattr(output, "tasks_output", None)
        if tasks_output and idx < len(tasks_output):
            return self._extract_from_item(tasks_output[idx], model, idx)

        # Manager-only fallback in some versions where direct output is returned.
        if idx == 0:
            return self._extract_from_item(output, model, idx)

        raise RuntimeError(f"Missing task output {idx}")

    def _extract_from_item(self, item: Any, model: Type[TModel], idx: int) -> TModel:
        pydantic_obj = getattr(item, "pydantic", None)
        if pydantic_obj is not None:
            return model.model_validate(pydantic_obj)

        json_dict = getattr(item, "json_dict", None)
        if json_dict is not None:
            return model.model_validate(json_dict)

        if isinstance(item, dict):
            return model.model_validate(item)
        if isinstance(item, BaseModel):
            return model.model_validate(item.model_dump(mode="json"))

        raw = str(getattr(item, "raw", item))
        try:
            return model.model_validate_json(raw)
        except Exception:
            pass

        match = re.search(r"\{.*\}", raw, flags=re.S)
        if not match:
            raise ValueError(f"Cannot parse JSON from task output {idx}")
        return model.model_validate(json.loads(match.group(0)))

    def _to_data_result(self, request: AnalysisRequest, draft: CrewDataAnalysisOutput) -> DataAnalysisResult:
        min_rate = self._clamp_rate(draft.recommended_discount_min)
        max_rate = self._clamp_rate(draft.recommended_discount_max)
        if min_rate > max_rate:
            min_rate, max_rate = max_rate, min_rate

        if draft.recommended_action == "maintain":
            min_rate, max_rate = 1.0, 1.0

        if request.risk_data.max_discount_allowed is not None:
            min_rate = max(min_rate, request.risk_data.max_discount_allowed)
            max_rate = max(min_rate, max_rate)

        confidence = self._clamp01(draft.recommendation_confidence)
        return DataAnalysisResult(
            sales_trend=draft.sales_trend,
            sales_trend_score=max(-1.0, min(1.0, float(draft.sales_trend_score))),
            inventory_status=draft.inventory_status,
            inventory_health_score=max(0.0, min(100.0, float(draft.inventory_health_score))),
            estimated_turnover_days=draft.estimated_turnover_days,
            demand_elasticity=draft.demand_elasticity,
            demand_elasticity_confidence=0.5 if draft.demand_elasticity is not None else None,
            product_lifecycle_stage=request.product.product_lifecycle_stage or "maturity",
            lifecycle_evidence="CrewAI analysis",
            has_anomalies=False,
            anomaly_list=[],
            recommended_action=draft.recommended_action,
            recommended_discount_range=(round(min_rate, 2), round(max_rate, 2)),
            recommendation_confidence=confidence,
            recommendation_reasons=draft.recommendation_reasons or ["CrewAI recommendation"],
            analysis_details={"engine": "crewai"},
            data_quality_score=1.0,
            limitations=[],
            thinking_process=draft.thinking_process.strip(),
            reasoning=draft.reasoning.strip(),
            decision_summary=draft.decision_summary.strip(),
            confidence=confidence,
        )

    def _to_market_result(self, draft: CrewMarketIntelOutput) -> MarketIntelResult:
        confidence = self._clamp01(draft.suggestion_confidence)
        return MarketIntelResult(
            competition_level=draft.competition_level,
            competition_score=self._clamp01(draft.competition_score),
            price_position=draft.price_position,
            price_percentile=self._clamp01(draft.price_percentile),
            min_competitor_price=draft.min_competitor_price,
            max_competitor_price=draft.max_competitor_price,
            avg_competitor_price=draft.avg_competitor_price,
            price_gap_vs_avg=draft.price_gap_vs_avg,
            active_competitor_promotions=[],
            upcoming_events=[],
            sentiment_score=0.0,
            sentiment_label="neutral",
            top_positive_keywords=[],
            top_negative_keywords=[],
            estimated_market_share=None,
            market_share_trend=None,
            market_suggestion=draft.market_suggestion,
            suggestion_confidence=confidence,
            suggestion_reasons=draft.suggestion_reasons or ["CrewAI recommendation"],
            analysis_details={"engine": "crewai"},
            data_sources=["crewai"],
            limitations=[],
            thinking_process=draft.thinking_process.strip(),
            reasoning=draft.reasoning.strip(),
            decision_summary=draft.decision_summary.strip(),
            confidence=confidence,
        )

    def _to_risk_result(self, request: AnalysisRequest, draft: CrewRiskControlOutput) -> RiskControlResult:
        current_price = max(float(request.product.current_price), 0.01)
        cost = max(float(request.product.cost), 0.0)

        break_even = max(cost, float(draft.break_even_price or 0.0))
        min_safe = max(break_even, float(draft.min_safe_price or break_even))
        required_min = max(min_safe, float(draft.required_min_price or min_safe))

        if request.risk_data.price_floor is not None:
            required_min = max(required_min, float(request.risk_data.price_floor))
        if request.risk_data.min_profit_markup is not None:
            required_min = max(required_min, cost * (1 + float(request.risk_data.min_profit_markup)))
        required_min = round(required_min, 2)

        calculated_compliant = current_price + 1e-6 >= required_min
        model_compliant = bool(draft.current_price_compliant)

        max_safe_discount = round(max(self._clamp_rate(draft.max_safe_discount), required_min / current_price), 2)
        allow_promotion = bool(draft.allow_promotion and calculated_compliant and max_safe_discount < 1.0)

        recommendation = draft.recommendation
        if not calculated_compliant:
            recommendation = "increase"
            allow_promotion = False
        elif not allow_promotion and recommendation == "discount":
            recommendation = "maintain"

        discounted_price = max(current_price * max_safe_discount, 0.01)
        margin_after = draft.profit_margin_after_discount
        if margin_after is None:
            margin_after = (discounted_price - break_even) / discounted_price

        warnings = list(draft.warnings or [])
        if model_compliant != calculated_compliant:
            warnings.append("Model compliance flag was adjusted by deterministic constraint check.")
        if not calculated_compliant:
            warnings.append(f"Current price is below required minimum {required_min:.2f}.")

        return RiskControlResult(
            current_profit_margin=float(draft.current_profit_margin),
            profit_margin_after_discount=float(margin_after),
            break_even_price=round(break_even, 2),
            min_safe_price=round(min_safe, 2),
            required_min_price=required_min,
            absolute_price_floor=request.risk_data.price_floor,
            current_price_compliant=calculated_compliant,
            risk_level=draft.risk_level,
            risk_score=max(0.0, min(100.0, float(draft.risk_score))),
            risk_breakdown={"composite": max(0.0, min(100.0, float(draft.risk_score)))},
            allow_promotion=allow_promotion,
            max_safe_discount=max_safe_discount,
            discount_conditions=draft.recommendation_reasons or [],
            warnings=self._dedupe(warnings),
            recommendation=recommendation,
            recommendation_reasons=draft.recommendation_reasons or ["CrewAI recommendation"],
            constraint_summary=self._dedupe((request.risk_data.constraint_summary or []) + (draft.constraint_summary or [])),
            calculation_details={"engine": "crewai"},
            compliance_check=calculated_compliant,
            veto_reason=draft.veto_reason if not allow_promotion else None,
            thinking_process=draft.thinking_process.strip(),
            reasoning=draft.reasoning.strip(),
            decision_summary=draft.decision_summary.strip(),
            confidence=round(max(0.2, min(1.0, 1.0 - float(draft.risk_score) / 100.0)), 4),
        )

    def _to_final_result(
        self,
        request: AnalysisRequest,
        draft: CrewManagerDecisionOutput,
        data_result: DataAnalysisResult,
        market_result: MarketIntelResult,
        risk_result: RiskControlResult,
    ) -> FinalDecision:
        current_price = max(float(request.product.current_price), 0.01)
        decision = draft.decision
        discount_rate = self._clamp_rate(draft.discount_rate)

        if decision == "increase":
            discount_rate = max(discount_rate, 1.0, risk_result.required_min_price / current_price)
            suggested = max(
                float(draft.suggested_price or 0.0),
                risk_result.required_min_price,
                current_price * discount_rate,
            )
        elif decision == "discount" and risk_result.allow_promotion:
            discount_rate = max(risk_result.max_safe_discount, min(1.0, discount_rate))
            suggested = current_price * discount_rate
            if discount_rate >= 0.999:
                decision = "maintain"
                suggested = current_price
                discount_rate = 1.0
        else:
            decision = "maintain"
            suggested = current_price
            discount_rate = 1.0

        if request.risk_data.price_ceiling is not None:
            suggested = min(float(request.risk_data.price_ceiling), float(suggested))
        suggested = round(float(suggested), 2)
        discount_rate = round(suggested / current_price, 4)

        confidence = self._clamp01(float(draft.confidence))
        outcomes = self._estimate_outcomes(decision, discount_rate, data_result, market_result, risk_result)

        summaries = [
            AgentSummary(
                agent_name="Data Analysis",
                summary=f"{data_result.sales_trend}/{data_result.inventory_status}",
                key_points=data_result.recommendation_reasons[:3],
            ),
            AgentSummary(
                agent_name="Market Intelligence",
                summary=f"{market_result.competition_level}/{market_result.price_position}",
                key_points=market_result.suggestion_reasons[:3],
            ),
            AgentSummary(
                agent_name="Risk Control",
                summary=f"{risk_result.risk_level}/allow={risk_result.allow_promotion}",
                key_points=risk_result.recommendation_reasons[:3],
            ),
        ]

        return FinalDecision(
            decision=decision,
            discount_rate=discount_rate,
            suggested_price=suggested,
            confidence=confidence,
            expected_outcomes=outcomes,
            core_reasons=draft.core_reasons or "CrewAI final decision",
            key_factors=draft.key_factors or [],
            conflicts_detected=[],
            risk_warning=draft.risk_warning or "No immediate blocking risk",
            contingency_plan=draft.contingency_plan or "Monitor KPI drift and rerun workflow if needed.",
            execution_plan=self._execution_plan(decision, suggested),
            report_text=f"Thinking: {draft.thinking_process}\nReasoning: {draft.reasoning}\nDecision: {decision} at {suggested:.2f}",
            agent_summaries=summaries,
            decision_framework="CrewAI sequential workflow",
            alternative_options=[{"option": "maintain"}, {"option": "bounded_discount", "rate": risk_result.max_safe_discount}],
            thinking_process=draft.thinking_process.strip(),
            reasoning=draft.reasoning.strip(),
            conflict_summary=draft.conflict_summary.strip(),
            warnings=risk_result.warnings[:3],
            agent_summaries_structured={
                "dataAnalysis": {
                    "salesTrend": data_result.sales_trend,
                    "inventoryStatus": data_result.inventory_status,
                },
                "marketIntel": {
                    "competitionLevel": market_result.competition_level,
                    "pricePosition": market_result.price_position,
                },
                "riskControl": {
                    "riskLevel": risk_result.risk_level,
                    "requiredMinPrice": risk_result.required_min_price,
                },
            },
        )

    def _estimate_outcomes(
        self,
        decision: str,
        discount_rate: float,
        data_result: DataAnalysisResult,
        market_result: MarketIntelResult,
        risk_result: RiskControlResult,
    ) -> ExpectedOutcomes:
        if decision == "increase":
            return ExpectedOutcomes(
                sales_lift=0.95,
                profit_change=max(0.0, discount_rate - 1.0),
                market_share_change=-0.01,
            )
        if decision == "maintain":
            return ExpectedOutcomes(sales_lift=1.0, profit_change=0.0, market_share_change=0.0)

        price_cut = max(0.0, 1.0 - discount_rate)
        elasticity = abs(data_result.demand_elasticity or -1.2)
        competition_bonus = 0.05 if market_result.competition_level == "fierce" else 0.0
        sales_lift = round(max(1.0, 1.0 + price_cut * elasticity + competition_bonus), 2)

        current_margin = max(0.0, risk_result.current_profit_margin)
        next_margin = max(0.0, risk_result.profit_margin_after_discount or current_margin)
        profit_change = round((sales_lift * next_margin - current_margin) / max(current_margin, 0.01), 3)
        market_share_change = round(min(0.1, price_cut * 0.6 + competition_bonus), 3)
        return ExpectedOutcomes(
            sales_lift=sales_lift,
            profit_change=profit_change,
            market_share_change=market_share_change,
        )

    def _execution_plan(self, decision: str, price: float) -> List[ExecutionPlan]:
        if decision == "increase":
            return [ExecutionPlan(step=1, action=f"Increase price to {price:.2f}", timing="immediately", responsible="ops")]
        if decision == "discount":
            return [ExecutionPlan(step=1, action=f"Discount price to {price:.2f}", timing="immediately", responsible="ops")]
        return [ExecutionPlan(step=1, action="Keep current price", timing="immediately", responsible="ops")]

    def _payload(self, request: AnalysisRequest) -> Dict[str, Any]:
        data = request.model_dump(mode="json")
        if len(data.get("customer_reviews", [])) > 20:
            data["customer_reviews"] = data["customer_reviews"][:20]
        return data

    def _data_prompt(self) -> str:
        return (
            "Input JSON:\n{request_json}\n\n"
            "You are the Data Analysis Specialist. Produce JSON only, no markdown.\n"
            "Required fields:\n"
            "- sales_trend in [rapid_rising,rising,stable,declining,rapid_declining]\n"
            "- sales_trend_score in [-1,1]\n"
            "- inventory_status in [severe_overstock,overstock,normal,tight,shortage]\n"
            "- inventory_health_score in [0,100]\n"
            "- estimated_turnover_days integer or null\n"
            "- demand_elasticity float or null\n"
            "- recommended_action in [maintain,discount,clearance]\n"
            "- recommended_discount_min, recommended_discount_max in [0.5,1.5]\n"
            "- recommendation_confidence in [0,1]\n"
            "- recommendation_reasons list[str]\n"
            "- thinking_process, reasoning, decision_summary strings\n"
            "Rules: recommended_discount_min <= recommended_discount_max. "
            "If recommended_action=maintain set both discount fields to 1.0."
        )

    def _market_prompt(self) -> str:
        return (
            "Input JSON:\n{request_json}\n\n"
            "You are the Market Intelligence Specialist. You may use prior task context. Produce JSON only.\n"
            "Required fields:\n"
            "- competition_level in [fierce,moderate,low]\n"
            "- competition_score in [0,1]\n"
            "- price_position in [premium,mid-range,budget]\n"
            "- price_percentile in [0,1]\n"
            "- min_competitor_price/max_competitor_price/avg_competitor_price/price_gap_vs_avg numbers or null\n"
            "- market_suggestion in [price_war,penetrate,discount,differentiate,premium,maintain]\n"
            "- suggestion_confidence in [0,1]\n"
            "- suggestion_reasons list[str]\n"
            "- thinking_process, reasoning, decision_summary strings."
        )

    def _risk_prompt(self) -> str:
        return (
            "Input JSON:\n{request_json}\n\n"
            "You are the Risk Control Specialist and hard-constraint gatekeeper. Produce JSON only.\n"
            "Required fields:\n"
            "- current_profit_margin, profit_margin_after_discount, break_even_price, min_safe_price, required_min_price\n"
            "- current_price_compliant bool\n"
            "- risk_level in [high,medium,low], risk_score in [0,100]\n"
            "- allow_promotion bool, max_safe_discount in [0.5,1.5]\n"
            "- recommendation in [maintain,discount,increase]\n"
            "- recommendation_reasons, constraint_summary, warnings lists[str]\n"
            "- veto_reason string or null\n"
            "- thinking_process, reasoning, decision_summary strings\n"
            "Rules: if current_price_compliant is false, recommendation must be increase and allow_promotion=false."
        )

    def _manager_prompt(self) -> str:
        return (
            "Input JSON:\n{request_json}\n\n"
            "You are the Decision Manager. Use context from all previous tasks and produce JSON only.\n"
            "Required fields:\n"
            "- decision in [maintain,discount,increase]\n"
            "- discount_rate in [0.5,1.5]\n"
            "- suggested_price number\n"
            "- confidence in [0,1]\n"
            "- core_reasons string\n"
            "- key_factors list[str]\n"
            "- risk_warning, contingency_plan, conflict_summary, thinking_process, reasoning strings\n"
            "Rule: if Risk Control indicates promotion is blocked, do not output decision=discount."
        )

    def _manager_only_prompt(self) -> str:
        return (
            "Input JSON:\n{manager_input_json}\n\n"
            "You are the Decision Manager. Data/market/risk outputs are already provided in the input.\n"
            "Produce JSON only with fields: decision, discount_rate, suggested_price, confidence, core_reasons, "
            "key_factors, risk_warning, contingency_plan, conflict_summary, thinking_process, reasoning.\n"
            "Rule: if risk_result.allow_promotion=false, decision cannot be discount."
        )

    def _ensure(self) -> None:
        if not self.is_available():
            raise RuntimeError(self.unavailable_reason())

    def _normalize_model(self, model_name: str) -> str:
        """
        CrewAI docs commonly use provider/model format.
        Keep already prefixed names intact, otherwise default to openai/ prefix.
        """
        cleaned = (model_name or "").strip()
        if not cleaned:
            return "openai/gpt-4o-mini"
        if "/" in cleaned:
            return cleaned
        return f"openai/{cleaned}"

    def _dump_json(self, payload: Dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False)

    def _clamp_rate(self, value: Optional[float], default: float = 1.0) -> float:
        if value is None:
            return default
        try:
            v = float(value)
        except Exception:
            return default
        return max(0.5, min(1.5, v))

    def _clamp01(self, value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def _dedupe(self, values: List[str]) -> List[str]:
        seen = set()
        items: List[str] = []
        for value in values:
            text = (value or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            items.append(text)
        return items


crewai_orchestrator = CrewAIOrchestrator()
