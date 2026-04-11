import logging

from sqlalchemy.orm import Session

from app.core.trace_context import bind_trace_context
from app.crew.protocols import CrewRunPayload
from app.repos.log_repo import LogRepo
from app.repos.result_repo import ResultRepo
from app.repos.task_repo import TaskRepo
from app.schemas.task import (
    AgentLogItem,
    DispatchTaskRequest,
    DispatchTaskResponse,
    TaskDetailResponse,
    TaskLogsResponse,
    TaskResultBrief,
    TaskStatusResponse,
)
from app.services.context_service import ContextService
from app.services.orchestration_service import OrchestrationService
from app.utils.crypto_utils import encrypt_api_key, decrypt_api_key
from app.utils.text_utils import is_manual_review_action, parse_constraints

logger = logging.getLogger(__name__)


class DispatchService:
    def __init__(self, db: Session):
        self.db = db
        self.task_repo = TaskRepo(db)
        self.result_repo = ResultRepo(db)
        self.log_repo = LogRepo(db)

    @staticmethod
    def _agent_code_by_order(order: int) -> str:
        mapping = {
            1: "DATA_ANALYSIS",
            2: "MARKET_INTEL",
            3: "RISK_CONTROL",
            4: "MANAGER_COORDINATOR",
        }
        return mapping.get(int(order or 0), "UNKNOWN")

    def _persist_llm_config(self, task, req: DispatchTaskRequest) -> None:
        """将用户 LLM 配置加密存入 task 记录（供 worker 和重试时恢复）。"""
        if not req.llm_api_key:
            return
        task.llm_api_key_enc = encrypt_api_key(req.llm_api_key)
        task.llm_base_url = req.llm_base_url
        task.llm_model = req.llm_model
        self.db.add(task)
        self.db.commit()

    def dispatch(self, req: DispatchTaskRequest, queue_service) -> DispatchTaskResponse:
        task = self.task_repo.get_by_id(req.task_id)
        if task is None:
            return DispatchTaskResponse(accepted=False, taskId=req.task_id, status="NOT_FOUND", message="task not found")

        # 无论任务当前状态如何，只要携带了 LLM 配置就立即写入 DB
        # （Java 插入任务时状态已为 QUEUED，必须在早返回之前持久化 Key）
        self._persist_llm_config(task, req)

        status = str(task.task_status or "").upper()
        if status == "COMPLETED":
            return DispatchTaskResponse(accepted=True, taskId=req.task_id, status="COMPLETED", message="already completed")
        if status in {"RUNNING", "QUEUED", "RETRYING"}:
            return DispatchTaskResponse(accepted=True, taskId=req.task_id, status=status, message="already accepted")
        if not queue_service.can_accept():
            self.task_repo.update_status(task, "FAILED", failure_reason="worker queue is full")
            return DispatchTaskResponse(accepted=False, taskId=req.task_id, status="FAILED", message="worker queue is full")

        self.task_repo.mark_queued(task, trace_id=req.trace_id)

        return DispatchTaskResponse(
            accepted=True,
            taskId=req.task_id,
            status="QUEUED",
            message=f"accepted, queue size {queue_service.queue_size()}",
        )

    def recover_pending_tasks(self, queue_service, max_retries: int) -> int:
        for task in self.task_repo.list_recoverable():
            status = str(task.task_status or "").upper()
            if status == "RUNNING":
                if int(task.retry_count or 0) >= max(max_retries, 0):
                    self.task_repo.mark_manual_review(task, "worker restarted after retry budget exhausted")
                    continue
                self.task_repo.mark_retrying(
                    task,
                    trace_id=task.trace_id,
                    failure_reason="worker restarted during execution",
                )
        return self.task_repo.count_dispatchable()

    def retry(self, req: DispatchTaskRequest, queue_service) -> DispatchTaskResponse:
        task = self.task_repo.get_by_id(req.task_id)
        if task is None:
            return DispatchTaskResponse(accepted=False, taskId=req.task_id, status="NOT_FOUND", message="task not found")
        if not queue_service.can_accept():
            self.task_repo.update_status(task, "FAILED", failure_reason="worker queue is full")
            return DispatchTaskResponse(accepted=False, taskId=req.task_id, status="FAILED", message="worker queue is full")

        self.task_repo.mark_retrying(task, trace_id=req.trace_id)
        return DispatchTaskResponse(
            accepted=True,
            taskId=req.task_id,
            status="RETRYING",
            message=f"retry accepted, queue size {queue_service.queue_size()}",
        )

    def handle_worker_failure(self, req: DispatchTaskRequest, reason: str, max_retries: int) -> DispatchTaskResponse:
        task = self.task_repo.get_by_id(req.task_id)
        if task is None:
            return DispatchTaskResponse(accepted=False, taskId=req.task_id, status="NOT_FOUND", message="task not found")

        status = str(task.task_status or "").upper()
        if status == "CANCELLED":
            return DispatchTaskResponse(accepted=False, taskId=req.task_id, status="CANCELLED", message="task cancelled")

        if int(task.retry_count or 0) >= max(max_retries, 0):
            self.task_repo.mark_manual_review(task, reason)
            return DispatchTaskResponse(
                accepted=False,
                taskId=req.task_id,
                status="MANUAL_REVIEW",
                message="retry budget exhausted",
            )

        self.task_repo.mark_retrying(task, trace_id=req.trace_id, failure_reason=reason)
        return DispatchTaskResponse(
            accepted=True,
            taskId=req.task_id,
            status="RETRYING",
            message="worker failure scheduled for retry",
        )

    def get_status(self, task_id: int) -> TaskStatusResponse:
        task = self.task_repo.get_by_id(task_id)
        if task is None:
            return TaskStatusResponse(taskId=task_id, status="NOT_FOUND", hasResult=False, message="task not found")
        result = self.result_repo.get_by_task_id(task_id)
        return TaskStatusResponse(taskId=task_id, status=task.task_status, hasResult=result is not None)

    def get_detail(self, task_id: int) -> TaskDetailResponse:
        task = self.task_repo.get_by_id(task_id)
        if task is None:
            raise ValueError(f"task not found: {task_id}")

        result_entity = self.result_repo.get_by_task_id(task_id)
        result = None
        if result_entity is not None:
            result = TaskResultBrief(
                finalPrice=result_entity.final_price,
                expectedSales=result_entity.expected_sales,
                expectedProfit=result_entity.expected_profit,
                profitGrowth=result_entity.profit_growth,
                isPass=(result_entity.is_pass == 1),
                executeStrategy=result_entity.execute_strategy,
                resultSummary=result_entity.result_summary,
            )

        return TaskDetailResponse(
            taskId=task.id,
            status=task.task_status,
            productId=task.product_id,
            currentPrice=task.current_price,
            suggestedMinPrice=task.suggested_min_price,
            suggestedMaxPrice=task.suggested_max_price,
            createdAt=task.created_at,
            updatedAt=task.updated_at,
            hasResult=result_entity is not None,
            result=result,
        )

    def get_logs(self, task_id: int, limit: int = 200) -> TaskLogsResponse:
        logs = self.log_repo.list_by_task_id(task_id, limit=limit)
        items: list[AgentLogItem] = []
        for item in logs:
            order = int(item.display_order or item.speak_order or 0)
            suggestion = item.suggestion_json if isinstance(item.suggestion_json, dict) else {}
            evidence = item.evidence_json if isinstance(item.evidence_json, list) else []
            thinking = item.thinking_summary or item.thought_content or ""
            action = str(suggestion.get("action") or "")

            items.append(
                AgentLogItem(
                    id=item.id,
                    taskId=item.task_id,
                    roleName=item.role_name,
                    speakOrder=item.speak_order,
                    thoughtContent=item.thought_content,
                    agentCode=self._agent_code_by_order(order),
                    agentName=item.role_name,
                    runOrder=order,
                    displayOrder=order,
                    stage="completed",
                    runStatus="success",
                    outputSummary=thinking,
                    needManualReview=is_manual_review_action(action),
                    thinking=thinking,
                    evidence=evidence,
                    suggestion=suggestion,
                    reasonWhy=item.final_reason,
                    createdAt=item.created_at,
                )
            )

        return TaskLogsResponse(taskId=task_id, total=len(items), logs=items)

    def build_dispatch_request(self, task) -> DispatchTaskRequest:
        llm_api_key = None
        if task.llm_api_key_enc:
            try:
                llm_api_key = decrypt_api_key(task.llm_api_key_enc)
            except Exception:
                logger.warning("Failed to decrypt LLM API key for task %s", task.id)

        return DispatchTaskRequest(
            taskId=task.id,
            productId=task.product_id,
            productIds=[task.product_id],
            strategyGoal=(task.strategy_goal or "MAX_PROFIT"),
            constraints=task.constraint_text or "",
            traceId=task.trace_id,
            llmApiKey=llm_api_key,
            llmBaseUrl=task.llm_base_url,
            llmModel=task.llm_model,
        )

    def execute_queued(self, req: DispatchTaskRequest, worker_id: int | None = None) -> None:
        task = self.task_repo.get_by_id(req.task_id)
        if task is None:
            raise ValueError(f"task not found: {req.task_id}")

        with bind_trace_context(trace_id=req.trace_id or task.trace_id or f"task-{req.task_id}", task_id=req.task_id):
            if str(task.task_status or "").upper() == "CANCELLED":
                logger.info("Worker %s skipped cancelled task %s", worker_id, req.task_id)
                return

            logger.info("Worker %s started task %s", worker_id, req.task_id)
            task.failure_reason = None
            self.db.add(task)
            self.db.commit()

            context_service = ContextService(self.db)
            try:
                product = context_service.load_product_context(req.product_id or 0)
                metrics = context_service.load_daily_metrics(product.product_id, limit=30)
                traffic = context_service.load_traffic(product.product_id, limit=30)
                baseline_sales = context_service.infer_baseline_sales(metrics, product.stock)
                baseline_profit = context_service.infer_baseline_profit(
                    current_price=product.current_price,
                    cost_price=product.cost_price,
                    monthly_sales=baseline_sales,
                )
                task.baseline_profit = baseline_profit
                self.db.add(task)
                self.db.commit()

                payload = CrewRunPayload(
                    task_id=req.task_id,
                    strategy_goal=req.strategy_goal,
                    constraints=parse_constraints(req.constraints),
                    product=product,
                    metrics=metrics,
                    traffic=traffic,
                    baseline_sales=baseline_sales,
                    baseline_profit=baseline_profit,
                    llm_api_key=req.llm_api_key,
                    llm_base_url=req.llm_base_url,
                    llm_model=req.llm_model,
                )
                if str(self.task_repo.get_by_id(req.task_id).task_status or "").upper() == "CANCELLED":
                    logger.info("Worker %s aborted cancelled task %s before orchestration", worker_id, req.task_id)
                    return
                orchestration_service = OrchestrationService(self.db)
                orchestration_service.run(payload)

                # 任务完成后清空加密的 API Key
                task_after = self.task_repo.get_by_id(req.task_id)
                if task_after and task_after.llm_api_key_enc:
                    task_after.llm_api_key_enc = None
                    self.db.add(task_after)
                    self.db.commit()
            except Exception:
                logger.exception("Worker execution failed for task %s", req.task_id)
                self.db.rollback()
                raise
