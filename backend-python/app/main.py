import asyncio
import sys

from fastapi import FastAPI

from app.api.decision_stream import router as decision_stream_router
from app.api.health import router as health_router
from app.api.internal_tasks import router as internal_tasks_router
from app.core.config import get_settings
from app.core.logger import configure_logging
from app.db.migrations import ensure_agent_run_log_schema

# Windows + Python 3.13 下，统一使用 Selector 事件循环提升连接稳定性。
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

configure_logging()
settings = get_settings()

app = FastAPI(title=settings.app_name)


@app.on_event("startup")
def startup_migrations() -> None:
    """服务启动时执行必要的轻量兜底迁移。"""
    ensure_agent_run_log_schema(settings.mysql_db)


app.include_router(health_router)
app.include_router(internal_tasks_router, prefix=settings.python_base_prefix)
app.include_router(decision_stream_router)
