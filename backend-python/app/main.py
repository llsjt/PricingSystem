import asyncio
import sys

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.internal_tasks import router as internal_tasks_router
from app.core.config import get_settings
from app.core.logger import configure_logging

# Windows + Python 3.13 场景下，Proactor 事件循环在 uvicorn 接收连接时可能出现 WinError 10014。
# 这里统一切换到 Selector 策略，提升服务启动和连接稳定性。
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

configure_logging()
settings = get_settings()

app = FastAPI(title=settings.app_name)
app.include_router(health_router)
app.include_router(internal_tasks_router, prefix=settings.python_base_prefix)
