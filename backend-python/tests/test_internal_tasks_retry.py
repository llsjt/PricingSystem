import asyncio
from decimal import Decimal
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api import internal_tasks
from app.db.base import Base
from app.models.pricing_task import PricingTask
from app.models.user_llm_config import UserLlmConfig
from app.schemas.task import RetryTaskRequest
from app.utils.crypto_utils import encrypt_api_key


def build_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[PricingTask.__table__, UserLlmConfig.__table__])
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)()


def create_task(db: Session, *, task_id: int, status: str, requested_by_user_id: int | None) -> PricingTask:
    task = PricingTask(
        id=task_id,
        task_code=f"TASK-{task_id}",
        shop_id=1,
        product_id=1000 + task_id,
        current_price=Decimal("19.90"),
        baseline_profit=Decimal("10.00"),
        task_status=status,
        strategy_goal="MAX_PROFIT",
        constraint_text="",
        trace_id=f"trace-{task_id}",
        retry_count=0,
        requested_by_user_id=requested_by_user_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def test_retry_task_refreshes_llm_snapshot_from_user_config(monkeypatch):
    db = build_session()
    task = create_task(db, task_id=701, status="FAILED", requested_by_user_id=9)
    task.llm_api_key_enc = None
    task.llm_base_url = None
    task.llm_model = None
    db.add(task)
    db.commit()
    db.refresh(task)
    db.add(
        UserLlmConfig(
            id=1,
            user_id=9,
            llm_api_key_enc=encrypt_api_key("sk-user"),
            llm_base_url="https://user.example.com/v1",
            llm_model="user-model",
        )
    )
    db.commit()
    published = {}

    class StubPublisher:
        async def publish_task(self, task_id, trace_id):  # noqa: ANN001
            published["task_id"] = task_id
            published["trace_id"] = trace_id

    monkeypatch.setattr("app.api.internal_tasks.get_dispatch_publisher_service", lambda: StubPublisher())

    response = asyncio.run(
        internal_tasks.retry_task(
            task.id,
            RetryTaskRequest(productId=task.product_id),
            db,
        )
    )
    refreshed = db.get(PricingTask, task.id)

    assert response.accepted is True
    assert response.status == "RETRYING"
    assert refreshed is not None
    assert refreshed.task_status == "RETRYING"
    assert refreshed.llm_api_key_enc is not None
    assert refreshed.llm_base_url == "https://user.example.com/v1"
    assert refreshed.llm_model == "user-model"
    assert published == {"task_id": task.id, "trace_id": task.trace_id}


def test_retry_task_rejects_when_user_llm_config_missing(monkeypatch):
    db = build_session()
    task = create_task(db, task_id=702, status="FAILED", requested_by_user_id=10)

    class StubPublisher:
        async def publish_task(self, task_id, trace_id):  # noqa: ANN001
            raise AssertionError("publish_task should not be called")

    monkeypatch.setattr("app.api.internal_tasks.get_dispatch_publisher_service", lambda: StubPublisher())

    try:
        asyncio.run(
            internal_tasks.retry_task(
                task.id,
                RetryTaskRequest(productId=task.product_id),
                db,
            )
        )
        raise AssertionError("expected retry_task to raise HTTPException")
    except HTTPException as exc:
        assert exc.status_code == 409
