"""内部任务接口模块，提供任务状态、详情、日志和重试等仅供 Java 后端调用的入口。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.trace_context import bind_trace_context
from app.core.security import verify_internal_token
from app.db.session import get_db
from app.repos.task_repo import TaskRepo
from app.schemas.task import (
    DispatchTaskRequest,
    DispatchTaskResponse,
    RetryTaskRequest,
    TaskDetailResponse,
    TaskLogsResponse,
    TaskStatusResponse,
)
from app.services.dispatch_service import DispatchService
from app.services.dispatch_publisher_service import get_dispatch_publisher_service
from app.services.task_recovery_service import TaskRecoveryService

router = APIRouter(
    prefix="/tasks",
    tags=["internal-tasks"],
    dependencies=[Depends(verify_internal_token)],
)

@router.get("/{task_id}/status", response_model=TaskStatusResponse)
def task_status(task_id: int, db: Session = Depends(get_db)) -> TaskStatusResponse:
    service = DispatchService(db)
    return service.get_status(task_id)


@router.get("/{task_id}/detail", response_model=TaskDetailResponse)
def task_detail(task_id: int, db: Session = Depends(get_db)) -> TaskDetailResponse:
    service = DispatchService(db)
    try:
        return service.get_detail(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{task_id}/logs", response_model=TaskLogsResponse)
def task_logs(
    task_id: int,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> TaskLogsResponse:
    task_repo = TaskRepo(db)
    if task_repo.get_by_id(task_id) is None:
        raise HTTPException(status_code=404, detail="task not found")

    service = DispatchService(db)
    return service.get_logs(task_id, limit=limit)


@router.post("/recover-stale")
async def recover_stale_tasks(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    result = await TaskRecoveryService(db).recover_once_async(
        lease_timeout_seconds=settings.running_lease_timeout_seconds,
        max_retries=settings.agent_max_retries,
        batch_size=settings.recovery_batch_size,
        dispatch_republish_seconds=settings.dispatch_republish_seconds,
    )
    return {
        "scanned": result.scanned,
        "requeued": result.requeued,
        "failed": result.failed,
        "republished": result.republished,
        "skipped": result.skipped,
        "publishFailed": result.publish_failed,
    }


@router.post("/{task_id}/retry", response_model=DispatchTaskResponse)
async def retry_task(
    task_id: int,
    payload: RetryTaskRequest,
    db: Session = Depends(get_db),
) -> DispatchTaskResponse:
    task_repo = TaskRepo(db)
    task = task_repo.get_by_id(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")

    req = DispatchTaskRequest(
        taskId=task_id,
        productId=payload.product_id or task.product_id,
        productIds=[payload.product_id or task.product_id],
        strategyGoal=payload.strategy_goal or task.strategy_goal or "MAX_PROFIT",
        constraints=payload.constraints if payload.constraints is not None else (task.constraint_text or ""),
        traceId=task.trace_id,
    )
    with bind_trace_context(trace_id=req.trace_id or f"task-{task_id}", task_id=task_id):
        service = DispatchService(db)
        try:
            service.refresh_task_llm_snapshot_from_user_config(task)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        updated = task_repo.mark_retrying(task, trace_id=req.trace_id)
        await get_dispatch_publisher_service().publish_task(updated.id, updated.trace_id)
        return DispatchTaskResponse(
            accepted=True,
            taskId=task_id,
            status="RETRYING",
            message="retry accepted",
        )
