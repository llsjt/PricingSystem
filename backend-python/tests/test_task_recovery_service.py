from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.pricing_task import PricingTask
from app.services.task_recovery_service import TaskRecoveryService


class FakePublisher:
    def __init__(self):
        self.published: list[tuple[int, str | None]] = []

    async def publish_task(self, task_id: int, trace_id: str | None) -> None:
        self.published.append((task_id, trace_id))


def build_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[PricingTask.__table__])
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)()


def create_task(
    db: Session,
    *,
    task_id: int,
    status: str,
    execution_id: str | None,
    retry_count: int = 0,
    heartbeat_minutes_ago: int = 20,
) -> PricingTask:
    heartbeat = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=heartbeat_minutes_ago)
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
        retry_count=retry_count,
        consumer_retry_count=0,
        current_execution_id=execution_id,
        started_at=heartbeat,
        last_heartbeat_at=heartbeat,
        created_at=heartbeat,
        updated_at=heartbeat,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def test_recover_once_requeues_stale_running_task():
    db = build_session()
    publisher = FakePublisher()
    create_task(db, task_id=1, status="RUNNING", execution_id="exec-old", retry_count=0)
    service = TaskRecoveryService(db, publisher=publisher)

    result = service.recover_once(
        lease_timeout_seconds=300,
        max_retries=2,
        batch_size=10,
    )

    refreshed = db.get(PricingTask, 1)
    assert result.requeued == 1
    assert result.failed == 0
    assert publisher.published == [(1, "trace-1")]
    assert refreshed is not None
    assert refreshed.task_status == "RETRYING"
    assert refreshed.current_execution_id is None


def test_recover_once_does_not_touch_fresh_running_task():
    db = build_session()
    publisher = FakePublisher()
    create_task(db, task_id=2, status="RUNNING", execution_id="exec-live", retry_count=0, heartbeat_minutes_ago=1)
    service = TaskRecoveryService(db, publisher=publisher)

    result = service.recover_once(
        lease_timeout_seconds=300,
        max_retries=2,
        batch_size=10,
    )

    refreshed = db.get(PricingTask, 2)
    assert result.scanned == 0
    assert publisher.published == []
    assert refreshed is not None
    assert refreshed.task_status == "RUNNING"
    assert refreshed.current_execution_id == "exec-live"


def test_recover_once_fails_task_after_retry_budget_without_requeue():
    db = build_session()
    publisher = FakePublisher()
    create_task(db, task_id=3, status="RUNNING", execution_id="exec-old", retry_count=2)
    service = TaskRecoveryService(db, publisher=publisher)

    result = service.recover_once(
        lease_timeout_seconds=300,
        max_retries=2,
        batch_size=10,
    )

    refreshed = db.get(PricingTask, 3)
    assert result.requeued == 0
    assert result.failed == 1
    assert publisher.published == []
    assert refreshed is not None
    assert refreshed.task_status == "FAILED"
    assert refreshed.current_execution_id is None
