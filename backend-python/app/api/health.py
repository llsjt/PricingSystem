"""健康检查接口模块，对外提供存活、就绪和指标状态入口。"""

from sqlalchemy import text

from fastapi import APIRouter

from app.db.session import SessionLocal
from app.repos.task_repo import TaskRepo
from app.schemas.common import HealthResponse
from app.services.rabbitmq_worker_service import get_rabbitmq_worker_service

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
    """存活检查：只确认进程仍可响应，并回传当前 Worker 快照。"""
    return {
        "status": "ok",
        "rabbitmq": get_rabbitmq_worker_service().snapshot(),
    }


@router.get("/health/ready")
def health_ready() -> dict:
    """就绪检查：同时要求数据库可访问且 RabbitMQ Worker 已进入 ready 状态。"""
    db_ok = False
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    finally:
        db.close()

    worker = get_rabbitmq_worker_service()
    snapshot = worker.snapshot()
    return {
        "status": "ok" if db_ok and worker.ready else "degraded",
        "dbOk": db_ok,
        "rabbitmq": "ok" if worker.ready else "down",
        "worker": snapshot,
    }


@router.get("/health/metrics")
def health_metrics() -> dict:
    """指标快照：汇总数据库、Worker 和任务状态统计，供运维页面或探针采集。"""
    db_ok = False
    task_metrics = {}
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
        task_metrics = TaskRepo(db).metrics_snapshot()
    finally:
        db.close()

    worker = get_rabbitmq_worker_service()
    return {
        "status": "ok" if db_ok and worker.ready else "degraded",
        "dbOk": db_ok,
        "rabbitmq": "ok" if worker.ready else "down",
        "worker": worker.snapshot(),
        "tasks": task_metrics,
    }
