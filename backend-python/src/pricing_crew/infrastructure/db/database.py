"""数据库连接模块，初始化引擎、会话与依赖注入。"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from pricing_crew.infrastructure.config.runtime import settings


DATABASE_URL = settings.resolved_database_url()

engine_kwargs = {
    "pool_pre_ping": True,
    "future": True,
}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
