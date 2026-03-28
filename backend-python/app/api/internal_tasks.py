from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import verify_internal_token
from app.db.session import get_db
from app.repos.task_repo import TaskRepo
from app.schemas.task import DispatchTaskRequest, DispatchTaskResponse, RetryTaskRequest, TaskStatusResponse
from app.services.dispatch_service import DispatchService

router = APIRouter(
    prefix="/tasks",
    tags=["internal-tasks"],
    dependencies=[Depends(verify_internal_token)],
)


@router.post("/dispatch", response_model=DispatchTaskResponse)
def dispatch_task(
    request: DispatchTaskRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> DispatchTaskResponse:
    """
    Java 后端调用入口：
    1. 受理任务
    2. 后台触发 4-Agent 协作执行
    """
    service = DispatchService(db)
    return service.dispatch(request, background_tasks)


@router.get("/{task_id}/status", response_model=TaskStatusResponse)
def task_status(task_id: int, db: Session = Depends(get_db)) -> TaskStatusResponse:
    service = DispatchService(db)
    return service.get_status(task_id)


@router.post("/{task_id}/retry", response_model=DispatchTaskResponse)
def retry_task(
    task_id: int,
    payload: RetryTaskRequest,
    background_tasks: BackgroundTasks,
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
        strategyGoal=payload.strategy_goal or "MAX_PROFIT",
        constraints=payload.constraints or "",
    )
    service = DispatchService(db)
    return service.retry(req, background_tasks)

