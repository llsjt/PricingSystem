from decimal import Decimal
from queue import Empty, Queue
from threading import Thread
from time import perf_counter
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.crew.crew_factory import build_crew_bundle
from app.crew.protocols import CrewRunPayload
from app.schemas.agent import DataAgentOutput, MarketAgentOutput, RiskAgentOutput
from app.schemas.result import TaskFinalResult
from app.tools.log_writer_tool import LogWriterTool
from app.tools.result_writer_tool import ResultWriterTool
from app.utils.math_utils import money


class OrchestrationService:
    """Coordinate multi-agent collaboration and persist logs/results."""

    def __init__(self, db: Session):
        self.db = db
        self.bundle = build_crew_bundle()
        self.log_tool = LogWriterTool(db)
        self.result_tool = ResultWriterTool(db)

    @staticmethod
    def _to_jsonable(value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(money(value))
        if isinstance(value, dict):
            return {str(key): OrchestrationService._to_jsonable(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [OrchestrationService._to_jsonable(item) for item in value]
        return value

    @staticmethod
    def _run_crewai_with_deadline(
        payload: CrewRunPayload,
        decision_inputs: dict[str, Any],
        timeout_seconds: int,
    ) -> tuple[dict[str, Any] | None, Exception | None]:
        timeout_seconds = max(int(timeout_seconds or 0), 1)
        result_queue: Queue[tuple[str, Any]] = Queue(maxsize=1)

        def runner() -> None:
            try:
                from app.crew.crewai_runtime import run_crewai_session

                result_queue.put(("SUCCESS", run_crewai_session(payload, decision_inputs)))
            except Exception as exc:
                result_queue.put(("ERROR", exc))

        worker = Thread(target=runner, daemon=True, name=f"crewai-task-{payload.task_id}")
        worker.start()
        worker.join(timeout=timeout_seconds)

        if worker.is_alive():
            return None, TimeoutError(f"CrewAI session timed out after {timeout_seconds}s")

        try:
            status, value = result_queue.get_nowait()
        except Empty:
            return None, RuntimeError("CrewAI session ended without output")

        if status == "ERROR":
            if isinstance(value, Exception):
                return None, value
            return None, RuntimeError(str(value))

        if isinstance(value, dict):
            return value, None
        return {"rawOutput": str(value)}, None

    @staticmethod
    def _has_usable_crewai_hint(decision: dict[str, Any]) -> bool:
        price = decision.get("recommendedPrice")
        try:
            return price is not None and float(price) > 0
        except Exception:
            return False

    @staticmethod
    def _classify_crewai_error(err: Exception) -> dict[str, Any]:
        message = str(err)
        lowered = message.lower()

        if isinstance(err, TimeoutError):
            return {
                "phase": "SESSION_TIMEOUT",
                "summary": "CrewAI session timeout",
                "riskLevel": "MEDIUM",
            }
        if "execution timed out" in lowered or ("timed out after" in lowered and "task" in lowered):
            return {
                "phase": "TASK_TIMEOUT",
                "summary": "CrewAI inner task timeout",
                "riskLevel": "MEDIUM",
            }
        if "llm api timeout" in lowered or "readtimeout" in lowered or "timeoutexception" in lowered:
            return {
                "phase": "LLM_TIMEOUT",
                "summary": "LLM request timeout",
                "riskLevel": "MEDIUM",
            }
        if "http 401" in lowered or "unauthorized" in lowered:
            return {
                "phase": "AUTH_ERROR",
                "summary": "LLM/API auth error",
                "riskLevel": "HIGH",
            }
        return {
            "phase": "ERROR",
            "summary": "CrewAI runtime error",
            "riskLevel": "MEDIUM",
        }

    def _build_decision_inputs(
        self,
        payload: CrewRunPayload,
        data_result: DataAgentOutput,
        market_result: MarketAgentOutput,
        risk_result: RiskAgentOutput,
    ) -> dict[str, Any]:
        candidate_price = money((data_result.suggested_price + market_result.suggested_price) / Decimal("2"))
        return {
            "taskId": payload.task_id,
            "strategyGoal": payload.strategy_goal,
            "constraints": self._to_jsonable(payload.constraints),
            "product": {
                "productId": payload.product.product_id,
                "productName": payload.product.product_name,
                "currentPrice": float(money(payload.product.current_price)),
                "costPrice": float(money(payload.product.cost_price)),
            },
            "baseline": {
                "sales": int(payload.baseline_sales),
                "profit": float(money(payload.baseline_profit)),
            },
            "localSignals": {
                "candidatePrice": float(candidate_price),
                "data": {
                    "suggestedPrice": float(money(data_result.suggested_price)),
                    "suggestedMinPrice": float(money(data_result.suggested_min_price)),
                    "suggestedMaxPrice": float(money(data_result.suggested_max_price)),
                    "expectedSales": int(data_result.expected_sales),
                    "expectedProfit": float(money(data_result.expected_profit)),
                    "confidence": float(data_result.confidence),
                },
                "market": {
                    "suggestedPrice": float(money(market_result.suggested_price)),
                    "marketFloor": float(money(market_result.market_floor)),
                    "marketCeiling": float(money(market_result.market_ceiling)),
                    "confidence": float(market_result.confidence),
                    "simulatedSamples": int(market_result.simulated_samples),
                },
                "risk": {
                    "isPass": bool(risk_result.is_pass),
                    "suggestedPrice": float(money(risk_result.suggested_price)),
                    "safeFloorPrice": float(money(risk_result.safe_floor_price)),
                    "riskLevel": risk_result.risk_level,
                    "needManualReview": bool(risk_result.need_manual_review),
                },
            },
        }

    def _run_crewai_with_fallback(
        self,
        payload: CrewRunPayload,
        context_text: str,
        decision_inputs: dict[str, Any],
    ) -> dict[str, Any] | None:
        settings = get_settings()
        session_timeout = max(settings.crewai_session_timeout_seconds, 10)

        self.log_tool.write(
            task_id=payload.task_id,
            agent_code="CREWAI",
            agent_name="CrewAI协作引擎",
            run_status="RUNNING",
            input_summary=context_text,
            output_summary="CrewAI MVP session started",
            output_payload={
                "phase": "STARTED",
                "enabled": self.bundle.crewai_available,
                "mvpEnabled": settings.crewai_mvp_enabled,
                "sessionTimeoutSeconds": session_timeout,
                "decisionInputChars": len(str(decision_inputs)),
                "tuning": {
                    "maxIter": settings.crewai_agent_max_iter,
                    "maxExecutionSeconds": settings.crewai_agent_max_execution_seconds,
                    "maxRetryLimit": settings.crewai_agent_max_retry_limit,
                },
            },
            risk_level="LOW",
        )

        if not settings.crewai_mvp_enabled:
            self.log_tool.write(
                task_id=payload.task_id,
                agent_code="CREWAI",
                agent_name="CrewAI协作引擎",
                run_status="SUCCESS",
                input_summary=context_text,
                output_summary="CrewAI disabled by config, continue with local outputs",
                output_payload={"enabled": False, "reason": "CREWAI_MVP_ENABLED=false"},
                risk_level="LOW",
            )
            return None

        if not self.bundle.crewai_available:
            self.log_tool.write(
                task_id=payload.task_id,
                agent_code="CREWAI",
                agent_name="CrewAI协作引擎",
                run_status="SUCCESS",
                input_summary=context_text,
                output_summary="CrewAI package not available, continue with local outputs",
                output_payload={"enabled": False, "reason": "crewai-not-installed"},
                risk_level="LOW",
            )
            return None

        started = perf_counter()
        crewai_output, err = self._run_crewai_with_deadline(
            payload=payload,
            decision_inputs=decision_inputs,
            timeout_seconds=session_timeout,
        )
        elapsed_ms = int((perf_counter() - started) * 1000)

        if err is None:
            decision = crewai_output.get("decision", {}) if isinstance(crewai_output, dict) else {}
            has_hint = isinstance(decision, dict) and self._has_usable_crewai_hint(decision)
            self.log_tool.write(
                task_id=payload.task_id,
                agent_code="CREWAI",
                agent_name="CrewAI协作引擎",
                run_status="SUCCESS",
                input_summary=context_text,
                output_summary=(
                    f"CrewAI completed with usable decision ({elapsed_ms}ms)"
                    if has_hint
                    else f"CrewAI completed but decision unusable ({elapsed_ms}ms)"
                ),
                output_payload={
                    "phase": "SUCCESS",
                    "elapsedMs": elapsed_ms,
                    "decision": decision,
                    "raw": crewai_output,
                },
                suggested_price=money(decision.get("recommendedPrice")) if has_hint else None,
                confidence_score=decision.get("confidence") if has_hint else None,
                risk_level="LOW",
            )
            return decision if has_hint else None

        classified = self._classify_crewai_error(err)
        self.log_tool.write(
            task_id=payload.task_id,
            agent_code="CREWAI",
            agent_name="CrewAI协作引擎",
            run_status="FAILED",
            input_summary=context_text,
            output_summary=f"{classified['summary']} ({elapsed_ms}ms), fallback to local outputs",
            output_payload={
                "phase": classified["phase"],
                "elapsedMs": elapsed_ms,
                "sessionTimeoutSeconds": session_timeout,
                "error": str(err),
                "suggestions": [
                    "Check LLM API reachability/auth",
                    "Lower CREWAI_AGENT_MAX_EXEC_SECONDS",
                    "Lower CREWAI_LLM_TIMEOUT_SECONDS",
                    "Set CREWAI_LLM_MAX_RETRIES=0",
                ],
            },
            error_message=str(err),
            risk_level=classified["riskLevel"],
        )
        return None

    @staticmethod
    def _need_second_round(
        current_price: Decimal,
        data_price: Decimal,
        market_price: Decimal,
    ) -> bool:
        settings = get_settings()
        if not settings.crewai_enable_second_round:
            return False
        if current_price <= 0:
            return False
        spread = abs(money(data_price) - money(market_price))
        return (spread / money(current_price)) > Decimal("0.18")

    def run(self, payload: CrewRunPayload) -> TaskFinalResult:
        product = payload.product
        context_text = (
            f"task={payload.task_id}, product={product.product_name}, "
            f"strategy={payload.strategy_goal}, constraints={payload.constraints}"
        )

        # 先跑本地重计算，确保 LLM 波动时任务仍可完成。
        data_result = self.bundle.data_agent.run(
            product=payload.product,
            metrics=payload.metrics,
            traffic=payload.traffic,
            strategy_goal=payload.strategy_goal,
        )
        self.log_tool.write(
            task_id=payload.task_id,
            agent_code=self.bundle.data_agent.code,
            agent_name=self.bundle.data_agent.name,
            run_status="SUCCESS",
            input_summary=context_text,
            output_summary=data_result.summary,
            output_payload=data_result.model_dump(by_alias=True, mode="json"),
            suggested_price=data_result.suggested_price,
            predicted_profit=data_result.expected_profit,
            confidence_score=data_result.confidence,
            risk_level="MEDIUM",
        )

        market_result = self.bundle.market_agent.run(
            product=payload.product,
            strategy_goal=payload.strategy_goal,
        )
        self.log_tool.write(
            task_id=payload.task_id,
            agent_code=self.bundle.market_agent.code,
            agent_name=self.bundle.market_agent.name,
            run_status="SUCCESS",
            input_summary=context_text,
            output_summary=market_result.summary,
            output_payload=market_result.model_dump(by_alias=True, mode="json"),
            suggested_price=market_result.suggested_price,
            confidence_score=market_result.confidence,
            risk_level="MEDIUM",
        )

        candidate_price = money((data_result.suggested_price + market_result.suggested_price) / Decimal("2"))
        risk_result = self.bundle.risk_agent.run(
            current_price=payload.product.current_price,
            cost_price=payload.product.cost_price,
            candidate_price=candidate_price,
            constraints=payload.constraints,
        )
        self.log_tool.write(
            task_id=payload.task_id,
            agent_code=self.bundle.risk_agent.code,
            agent_name=self.bundle.risk_agent.name,
            run_status="SUCCESS",
            input_summary=f"candidate_price={candidate_price}, constraints={payload.constraints}",
            output_summary=risk_result.summary,
            output_payload=risk_result.model_dump(by_alias=True, mode="json"),
            suggested_price=risk_result.suggested_price,
            confidence_score=0.86,
            risk_level=risk_result.risk_level,
            need_manual_review=risk_result.need_manual_review,
        )

        if self._need_second_round(
            current_price=payload.product.current_price,
            data_price=data_result.suggested_price,
            market_price=market_result.suggested_price,
        ):
            spread = abs(data_result.suggested_price - market_result.suggested_price)
            second_strategy = (
                "MARKET_SHARE" if payload.strategy_goal.upper() == "MAX_PROFIT" else payload.strategy_goal
            )

            data_result = self.bundle.data_agent.run(
                product=payload.product,
                metrics=payload.metrics,
                traffic=payload.traffic,
                strategy_goal=second_strategy,
            )
            self.log_tool.write(
                task_id=payload.task_id,
                agent_code=self.bundle.data_agent.code,
                agent_name=f"{self.bundle.data_agent.name}(复议)",
                run_status="SUCCESS",
                input_summary=f"second round: spread={money(spread)} strategy={second_strategy}",
                output_summary=data_result.summary,
                output_payload=data_result.model_dump(by_alias=True, mode="json"),
                suggested_price=data_result.suggested_price,
                predicted_profit=data_result.expected_profit,
                confidence_score=data_result.confidence,
                risk_level="MEDIUM",
            )

            market_result = self.bundle.market_agent.run(product=payload.product, strategy_goal=second_strategy)
            self.log_tool.write(
                task_id=payload.task_id,
                agent_code=self.bundle.market_agent.code,
                agent_name=f"{self.bundle.market_agent.name}(复议)",
                run_status="SUCCESS",
                input_summary=f"second round: spread={money(spread)} strategy={second_strategy}",
                output_summary=market_result.summary,
                output_payload=market_result.model_dump(by_alias=True, mode="json"),
                suggested_price=market_result.suggested_price,
                confidence_score=market_result.confidence,
                risk_level="MEDIUM",
            )

            candidate_price = money((data_result.suggested_price + market_result.suggested_price) / Decimal("2"))
            risk_result = self.bundle.risk_agent.run(
                current_price=payload.product.current_price,
                cost_price=payload.product.cost_price,
                candidate_price=candidate_price,
                constraints=payload.constraints,
            )
            self.log_tool.write(
                task_id=payload.task_id,
                agent_code=self.bundle.risk_agent.code,
                agent_name=f"{self.bundle.risk_agent.name}(复议)",
                run_status="SUCCESS",
                input_summary=f"second round risk candidate_price={candidate_price}",
                output_summary=risk_result.summary,
                output_payload=risk_result.model_dump(by_alias=True, mode="json"),
                suggested_price=risk_result.suggested_price,
                confidence_score=0.86,
                risk_level=risk_result.risk_level,
                need_manual_review=risk_result.need_manual_review,
            )

        decision_inputs = self._build_decision_inputs(payload, data_result, market_result, risk_result)
        crewai_hint = self._run_crewai_with_fallback(payload, context_text, decision_inputs)

        manager_result = self.bundle.manager_agent.run(
            strategy_goal=payload.strategy_goal,
            current_price=payload.product.current_price,
            cost_price=payload.product.cost_price,
            baseline_profit=payload.baseline_profit,
            baseline_sales=payload.baseline_sales,
            data_result=data_result,
            market_result=market_result,
            risk_result=risk_result,
            crewai_hint=crewai_hint,
        )
        self.log_tool.write(
            task_id=payload.task_id,
            agent_code=self.bundle.manager_agent.code,
            agent_name=self.bundle.manager_agent.name,
            run_status="SUCCESS",
            input_summary="final decision",
            output_summary=manager_result.result_summary,
            output_payload=manager_result.model_dump(by_alias=True, mode="json"),
            suggested_price=manager_result.final_price,
            predicted_profit=manager_result.expected_profit,
            confidence_score=0.82 if manager_result.is_pass else 0.58,
            risk_level="LOW" if manager_result.is_pass else "HIGH",
            need_manual_review=not manager_result.is_pass,
        )

        final_payload = TaskFinalResult(
            taskId=payload.task_id,
            finalPrice=manager_result.final_price,
            expectedSales=manager_result.expected_sales,
            expectedProfit=manager_result.expected_profit,
            profitGrowth=manager_result.profit_growth,
            isPass=manager_result.is_pass,
            executeStrategy=manager_result.execute_strategy,
            resultSummary=manager_result.result_summary,
            suggestedMinPrice=manager_result.suggested_min_price,
            suggestedMaxPrice=manager_result.suggested_max_price,
        )
        self.result_tool.write_final_result(final_payload)
        return final_payload
