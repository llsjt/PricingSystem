import logging

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.repos.task_repo import TaskRepo
from app.repos.result_repo import ResultRepo
from app.schemas.task import DispatchTaskRequest, DispatchTaskResponse, TaskStatusResponse
from app.services.context_service import ContextService
from app.services.orchestration_service import OrchestrationService
from app.tools.log_writer_tool import LogWriterTool
from app.crew.protocols import CrewRunPayload
from app.utils.text_utils import parse_constraints

logger = logging.getLogger(__name__)


class DispatchService:
    """任务派发服务：只做任务受理、状态流转和后台执行调度。"""

    def __init__(self, db: Session):
        self.db = db
        self.task_repo = TaskRepo(db)
        self.result_repo = ResultRepo(db)

    def dispatch(self, req: DispatchTaskRequest, background_tasks: BackgroundTasks) -> DispatchTaskResponse:
        # 幂等受理：避免重复派发同一个 task
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

    @staticmethod
    def _run_background(payload: dict) -> None:
        db = SessionLocal()
        try:
            req = DispatchTaskRequest.model_validate(payload)
            service = DispatchService(db)
            service._execute(req)
        except Exception:
            logger.exception("Background dispatch execution failed")
        finally:
            db.close()

    def _execute(self, req: DispatchTaskRequest) -> None:
        # 后台执行入口：聚合上下文 -> 多 Agent 协作 -> 落库结果
        task = self.task_repo.get_by_id(req.task_id)
        if task is None:
            raise ValueError(f"task not found: {req.task_id}")

        context_service = ContextService(self.db)
        log_tool = LogWriterTool(self.db)
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
        except Exception as exc:
            self.task_repo.update_status(task, "FAILED")
            log_tool.write(
                task_id=req.task_id,
                agent_code="SYSTEM",
                agent_name="系统调度",
                run_status="FAILED",
                input_summary=f"strategy={req.strategy_goal}",
                output_summary="任务执行失败",
                output_payload={"error": str(exc)},
                error_message=str(exc),
                need_manual_review=True,
                risk_level="HIGH",
            )
            raise
