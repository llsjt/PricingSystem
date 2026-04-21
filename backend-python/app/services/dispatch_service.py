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
from app.utils.crypto_utils import decrypt_task_api_key, encrypt_api_key
from app.utils.text_utils import MANUAL_REVIEW_STRATEGY, is_manual_review_action, parse_constraints

logger = logging.getLogger(__name__)


class DispatchService:
    """任务派发服务，负责队列接入、失败重试、日志整理和进入编排前的上下文准备。"""

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

    @staticmethod
    def _normalize_log_stage(stage: str | None, suggestion: dict) -> str:
        normalized = str(stage or "").strip().lower()
        if normalized == "running":
            return "running"
        if normalized == "failed" or suggestion.get("error") is True:
            return "failed"
        return "completed"

    def _store_llm_config(self, task, req: DispatchTaskRequest) -> None:
        if not req.llm_api_key:
            return
        task.llm_api_key_enc = encrypt_api_key(req.llm_api_key)
        task.llm_base_url = req.llm_base_url
        task.llm_model = req.llm_model
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

    def dispatch(self, req: DispatchTaskRequest, queue_service) -> DispatchTaskResponse:
        """把 Java 侧送来的任务纳入本地执行队列，并同步保存本次执行需要的 LLM 配置。"""
        task = self.task_repo.get_by_id(req.task_id)
        if task is None:
            return DispatchTaskResponse(accepted=False, taskId=req.task_id, status="NOT_FOUND", message="task not found")

        status = str(task.task_status or "").upper()
        if status == "COMPLETED":
            return DispatchTaskResponse(accepted=True, taskId=req.task_id, status="COMPLETED", message="already completed")
        if status in {"RUNNING", "QUEUED", "RETRYING"}:
            self._store_llm_config(task, req)
            return DispatchTaskResponse(accepted=True, taskId=req.task_id, status=status, message="already accepted")
        if not queue_service.can_accept():
            self.task_repo.update_status(task, "FAILED", failure_reason="worker queue is full")
            return DispatchTaskResponse(accepted=False, taskId=req.task_id, status="FAILED", message="worker queue is full")

        # 先写入 LLM 配置，再设为 QUEUED —— 保证 worker 领到任务时 Key 已在 DB 中
        # （Java 插入时状态为 PENDING，worker 只认 QUEUED，因此不存在竞态）
        self._store_llm_config(task, req)

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
                    self.task_repo.update_status(task, "FAILED", failure_reason="worker restarted after retry budget exhausted")
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
        """处理 Worker 执行失败后的重试状态流转，并保留可用于断点续跑的成功卡片。"""
        task = self.task_repo.get_by_id(req.task_id)
        if task is None:
            return DispatchTaskResponse(accepted=False, taskId=req.task_id, status="NOT_FOUND", message="task not found")

        status = str(task.task_status or "").upper()
        if status == "CANCELLED":
            return DispatchTaskResponse(accepted=False, taskId=req.task_id, status="CANCELLED", message="task cancelled")

        if int(task.retry_count or 0) >= max(max_retries, 0):
            self.task_repo.update_status(task, "FAILED", failure_reason=reason)
            return DispatchTaskResponse(
                accepted=False,
                taskId=req.task_id,
                status="FAILED",
                message="retry budget exhausted",
            )

        # Agent 粒度断点续跑：只清理本轮 retry_count 下的 running/failed 占位，
        # 保留上一轮 completed 的卡片（ResumeService 用它们判断可跳过的前缀集）。
        self.log_repo.delete_running_and_failed_by_run_attempt(
            task.id, int(task.retry_count or 0)
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
                executeStrategy=MANUAL_REVIEW_STRATEGY,
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
        """把数据库日志整理成前端日志卡片结构，补齐运行阶段和人工审核等兼容字段。"""
        logs = self.log_repo.list_by_task_id(task_id, limit=limit)
        items: list[AgentLogItem] = []
        for item in logs:
            order = int(item.display_order or item.speak_order or 0)
            suggestion = item.suggestion_json if isinstance(item.suggestion_json, dict) else {}
            if "strategy" in suggestion:
                suggestion = {**suggestion, "strategy": MANUAL_REVIEW_STRATEGY}
            evidence = item.evidence_json if isinstance(item.evidence_json, list) else []
            thinking = item.thinking_summary or item.thought_content or ""
            action = str(suggestion.get("action") or "")
            stage = self._normalize_log_stage(item.stage, suggestion)
            run_status = "running" if stage == "running" else "failed" if stage == "failed" else "success"

            items.append(
                AgentLogItem(
                    id=item.id,
                    taskId=item.task_id,
                    roleName=item.role_name,
                    speakOrder=item.speak_order,
                    thoughtContent=item.thought_content,
                    agentCode=self._agent_code_by_order(order),
                    agentName=item.role_name,
                    runAttempt=max(int(item.run_attempt or 0), 0),
                    runOrder=order,
                    displayOrder=order,
                    stage=stage,
                    runStatus=run_status,
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
        """把数据库任务实体重新组装成一次可执行的派发请求，供重试和恢复场景复用。"""
        llm_api_key = None
        if task.llm_api_key_enc:
            try:
                llm_api_key = decrypt_task_api_key(task.llm_api_key_enc)
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

    def execute_queued_by_task_id(self, task_id: int, execution_id: str) -> None:
        task = self.task_repo.get_by_id(task_id)
        if task is None:
            raise ValueError(f"task not found: {task_id}")
        # RabbitMQ 消费、重试和恢复场景都会先收敛成统一的派发请求，再复用主执行流程。
        request = self.build_dispatch_request(task)
        self.execute_queued(request, execution_id=execution_id)

    def execute_queued(
        self,
        req: DispatchTaskRequest,
        worker_id: int | None = None,
        execution_id: str | None = None,
    ) -> None:
        """真正执行队列中的任务：补齐上下文、进入 CrewAI 编排，并在结束后清理临时密钥。"""
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

            # 先把商品上下文、近 30 天指标和基线利润算出来，再交给多智能体编排层统一消费。
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
                # 编排前再做一次取消判断，避免用户取消后仍继续调用大模型和写日志。
                if str(self.task_repo.get_by_id(req.task_id).task_status or "").upper() == "CANCELLED":
                    logger.info("Worker %s aborted cancelled task %s before orchestration", worker_id, req.task_id)
                    return
                orchestration_service = OrchestrationService(self.db, execution_id=execution_id)
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
