from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.internal_tasks import router as internal_tasks_router
from app.core.config import get_settings
from app.core.logger import configure_logging

configure_logging()
settings = get_settings()

app = FastAPI(title=settings.app_name)
app.include_router(health_router)
app.include_router(internal_tasks_router, prefix=settings.python_base_prefix)

