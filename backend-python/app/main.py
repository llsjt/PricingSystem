import asyncio
import logging
import sys
import time

from fastapi import FastAPI, Request

from app.api.health import router as health_router
from app.api.internal_tasks import router as internal_tasks_router
from app.core.config import get_settings
from app.core.logger import configure_logging
from app.core.trace_context import bind_trace_context
from app.db.migrations import ensure_agent_run_log_schema
from app.services.task_queue_service import get_task_queue_service

# Windows + Python 3.13 下，统一使用 Selector 事件循环提升连接稳定性。
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

configure_logging()
settings = get_settings()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)


@app.middleware("http")
async def trace_logging_middleware(request: Request, call_next):
    trace_id = (request.headers.get("X-Trace-Id") or "").strip() or f"req-{int(time.time() * 1000)}"
    request.state.trace_id = trace_id
    started_at = time.perf_counter()
    with bind_trace_context(trace_id=trace_id):
        logger.info("HTTP request started %s %s", request.method, request.url.path)
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        response.headers["X-Trace-Id"] = trace_id
        logger.info(
            "HTTP request completed %s %s status=%s durationMs=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response


@app.on_event("startup")
async def startup_migrations() -> None:
    settings.validate_production_safety()
    competitor_problems = settings.validate_competitor_source()
    if competitor_problems:
        raise RuntimeError("Unsafe competitor configuration: " + ", ".join(competitor_problems))
    ensure_agent_run_log_schema(settings.mysql_db)
    queue_service = get_task_queue_service()
    await queue_service.start()
    queue_service.recover_pending_tasks()


@app.on_event("shutdown")
async def shutdown_queue() -> None:
    await get_task_queue_service().stop()


app.include_router(health_router)
app.include_router(internal_tasks_router, prefix=settings.python_base_prefix)
