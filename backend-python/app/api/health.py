from sqlalchemy import text

from fastapi import APIRouter

from app.db.session import SessionLocal
from app.schemas.common import HealthResponse

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

