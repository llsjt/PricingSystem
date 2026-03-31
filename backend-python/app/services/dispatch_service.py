import logging
from typing import Any

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.crew.protocols import CrewRunPayload
from app.db.session import SessionLocal
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
from app.utils.text_utils import is_manual_review_action, parse_constraints

logger = logging.getLogger(__name__)


class DispatchService:
    """任务分发服务：Java 触发后异步执行 4 Agent MVP。"""

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

    def dispatch(self, req: DispatchTaskRequest, background_tasks: BackgroundTasks) -> DispatchTaskResponse:
        # 幂等受理：避免重复派发同一个 task。
        task = self.task_repo.get_by_id(req.task_id)
        if task is None:
            return DispatchTaskResponse(accepted=False, taskId=req.task_id, status="NOT_FOUND", message="task not found")

        if task.task_status == "COMPLETED":
            return DispatchTaskResponse(accepted=True, taskId=req.task_id, status="COMPLETED", message="already completed")
        if task.task_status == "RUNNING":
            return DispatchTaskResponse(accepted=True, taskId=req.task_id, status="RUNNING", message="already running")

        self.task_repo.update_status(task, "RUNNING")
        payload = req.model_dump()
        background_tasks.add_task(self._run_background, payload)
        return DispatchTaskResponse(accepted=True, taskId=req.task_id, status="RUNNING", message="accepted")

    def get_status(self, task_id: int) -> TaskStatusResponse:
        task = self.task_repo.get_by_id(task_id)
        if task is None:
            return TaskStatusResponse(taskId=task_id, status="NOT_FOUND", hasResult=False, message="task not found")
        result = self.result_repo.get_by_task_id(task_id)
        return TaskStatusResponse(taskId=task_id, status=task.task_status, hasResult=result is not None)

    def retry(self, req: DispatchTaskRequest, background_tasks: BackgroundTasks) -> DispatchTaskResponse:
        task = self.task_repo.get_by_id(req.task_id)
        if task is None:
            return DispatchTaskResponse(accepted=False, taskId=req.task_id, status="NOT_FOUND", message="task not found")
        self.task_repo.update_status(task, "RUNNING")
        payload = req.model_dump()
        background_tasks.add_task(self._run_background, payload)
        return DispatchTaskResponse(accepted=True, taskId=req.task_id, status="RUNNING", message="retry accepted")

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
                    stage="已完成",
                    runStatus="成功",
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

    @staticmethod
    def _run_background(payload: dict) -> None:
        db = SessionLocal()
        try:
            req = DispatchTaskRequest.model_validate(payload)
            service = DispatchService(db)
            service._execute(req)
        except Exception as exc:
            logger.exception("Background dispatch execution failed")
            # 确保错误信息在控制台可见，方便调试 CrewAI 执行问题
            print(f"[ERROR] Background dispatch failed: {exc}", flush=True)
        finally:
            db.close()

    def _execute(self, req: DispatchTaskRequest) -> None:
        """后台执行入口：聚合上下文 -> 顺序运行 4 Agent -> 结果落库。"""
        task = self.task_repo.get_by_id(req.task_id)
        if task is None:
            raise ValueError(f"task not found: {req.task_id}")

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
            )
            orchestration_service = OrchestrationService(self.db)
            orchestration_service.run(payload)
        except Exception:
            self.db.rollback()
            task = self.task_repo.get_by_id(req.task_id)
            if task is not None:
                self.task_repo.update_status(task, "FAILED")
            raise
