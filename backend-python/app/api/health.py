from sqlalchemy import text

from fastapi import APIRouter

from app.db.session import SessionLocal
from app.repos.task_repo import TaskRepo
from app.schemas.common import HealthResponse
from app.services.task_queue_service import get_task_queue_service

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """健康检查：用于部署时快速验证 Python 服务和数据库连通性。"""
    db_ok = False
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    finally:
        db.close()
    return HealthResponse(status="ok" if db_ok else "degraded", db_ok=db_ok)


@router.get("/health/live")
def health_live() -> dict:
    return {
        "status": "ok",
        "queue": get_task_queue_service().snapshot(),
    }


@router.get("/health/ready")
def health_ready() -> dict:
    db_ok = False
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    finally:
        db.close()

    queue = get_task_queue_service().snapshot()
    return {
        "status": "ok" if db_ok and queue["started"] else "degraded",
        "dbOk": db_ok,
        "queue": queue,
    }


@router.get("/health/metrics")
def health_metrics() -> dict:
    db_ok = False
    task_metrics = {}
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
        task_metrics = TaskRepo(db).metrics_snapshot()
    finally:
        db.close()

    queue = get_task_queue_service().snapshot()
    return {
        "status": "ok" if db_ok and queue["started"] else "degraded",
        "dbOk": db_ok,
        "queue": queue,
        "tasks": task_metrics,
    }
