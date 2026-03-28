from decimal import Decimal
from queue import Empty, Queue
from threading import Thread
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.crew.crew_factory import build_crew_bundle
from app.crew.protocols import CrewRunPayload
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
    def _run_crewai_with_deadline(
        payload: CrewRunPayload, timeout_seconds: int
    ) -> tuple[dict[str, Any] | None, Exception | None]:
        timeout_seconds = max(int(timeout_seconds or 0), 1)
        result_queue: Queue[tuple[str, Any]] = Queue(maxsize=1)

        def runner() -> None:
            try:
                from app.crew.crewai_runtime import run_crewai_session

                result_queue.put(("SUCCESS", run_crewai_session(payload)))
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

    def _run_crewai_with_fallback(self, payload: CrewRunPayload, context_text: str) -> None:
        settings = get_settings()
        session_timeout = max(settings.crewai_session_timeout_seconds, 10)

        self.log_tool.write(
            task_id=payload.task_id,
            agent_code="CREWAI",
            agent_name="CrewAI协作引擎",
            run_status="RUNNING",
            input_summary=context_text,
            output_summary="CrewAI 协作已启动，正在执行多 Agent 协商",
            output_payload={
                "phase": "STARTED",
                "enabled": self.bundle.crewai_available,
                "sessionTimeoutSeconds": session_timeout,
            },
            risk_level="LOW",
        )

        if not self.bundle.crewai_available:
            self.log_tool.write(
                task_id=payload.task_id,
                agent_code="CREWAI",
                agent_name="CrewAI协作引擎",
                run_status="SUCCESS",
                input_summary=context_text,
                output_summary="未检测到 CrewAI，已降级为本地多 Agent 编排",
                output_payload={"enabled": False},
                risk_level="LOW",
            )
            return

        crewai_output, err = self._run_crewai_with_deadline(
            payload=payload, timeout_seconds=session_timeout
        )
        if err is None:
            self.log_tool.write(
                task_id=payload.task_id,
                agent_code="CREWAI",
                agent_name="CrewAI协作引擎",
                run_status="SUCCESS",
                input_summary=context_text,
                output_summary="CrewAI 4-Agent 协作执行完成",
                output_payload=crewai_output,
                risk_level="LOW",
            )
            return

        if isinstance(err, TimeoutError):
            self.log_tool.write(
                task_id=payload.task_id,
                agent_code="CREWAI",
                agent_name="CrewAI协作引擎",
                run_status="FAILED",
                input_summary=context_text,
                output_summary=f"CrewAI 执行超时（>{session_timeout}s），已降级为本地多 Agent 继续执行",
                output_payload={"phase": "TIMEOUT", "error": str(err)},
                error_message=str(err),
                risk_level="MEDIUM",
            )
            return

        self.log_tool.write(
            task_id=payload.task_id,
            agent_code="CREWAI",
            agent_name="CrewAI协作引擎",
            run_status="FAILED",
            input_summary=context_text,
            output_summary="CrewAI 调用异常，已降级为本地多 Agent 继续执行",
            output_payload={"phase": "ERROR", "error": str(err)},
            error_message=str(err),
            risk_level="MEDIUM",
        )

    def run(self, payload: CrewRunPayload) -> TaskFinalResult:
        product = payload.product
        context_text = (
            f"task={payload.task_id}, product={product.product_name}, "
            f"strategy={payload.strategy_goal}, constraints={payload.constraints}"
        )

        self._run_crewai_with_fallback(payload, context_text)

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

        # Avoid a rigid one-pass pipeline: trigger re-negotiation when DATA/MARKET diverge a lot.
        spread = abs(data_result.suggested_price - market_result.suggested_price)
        if payload.product.current_price > 0 and spread / payload.product.current_price > Decimal("0.12"):
            second_strategy = "MARKET_SHARE" if payload.strategy_goal.upper() == "MAX_PROFIT" else payload.strategy_goal

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
                input_summary=f"二次协商触发: spread={money(spread)} second_strategy={second_strategy}",
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
                input_summary=f"二次协商触发: spread={money(spread)} second_strategy={second_strategy}",
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
                input_summary=f"二次风控 candidate_price={candidate_price}",
                output_summary=risk_result.summary,
                output_payload=risk_result.model_dump(by_alias=True, mode="json"),
                suggested_price=risk_result.suggested_price,
                confidence_score=0.86,
                risk_level=risk_result.risk_level,
                need_manual_review=risk_result.need_manual_review,
            )

        manager_result = self.bundle.manager_agent.run(
            strategy_goal=payload.strategy_goal,
            current_price=payload.product.current_price,
            cost_price=payload.product.cost_price,
            baseline_profit=payload.baseline_profit,
            baseline_sales=payload.baseline_sales,
            data_result=data_result,
            market_result=market_result,
            risk_result=risk_result,
        )
        self.log_tool.write(
            task_id=payload.task_id,
            agent_code=self.bundle.manager_agent.code,
            agent_name=self.bundle.manager_agent.name,
            run_status="SUCCESS",
            input_summary="综合裁决",
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
