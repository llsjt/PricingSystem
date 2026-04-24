from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.pricing_task import PricingTask
from app.repos.task_repo import TaskRepo


def build_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[PricingTask.__table__])
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)()


def create_task(db: Session, *, task_id: int, status: str, execution_id: str | None = None, consumer_retry_count: int = 0) -> PricingTask:
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
        consumer_retry_count=consumer_retry_count,
        current_execution_id=execution_id,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def test_acquire_execution_claims_unowned_task():
    db = build_session()
    create_task(db, task_id=1, status="QUEUED")
    repo = TaskRepo(db)

    assert repo.acquire_execution(1, "exec-1", allow_reclaim=False, max_retry=3) is True

    refreshed = db.get(PricingTask, 1)
    assert refreshed is not None
    assert refreshed.current_execution_id == "exec-1"
    assert refreshed.task_status == "RUNNING"
    assert refreshed.consumer_retry_count == 0


def test_acquire_execution_reclaims_redelivered_task_and_increments_retry_count():
    db = build_session()
    create_task(db, task_id=2, status="RUNNING", execution_id="exec-old", consumer_retry_count=0)
    repo = TaskRepo(db)

    assert repo.acquire_execution(2, "exec-new", allow_reclaim=True, max_retry=3) is True

    refreshed = db.get(PricingTask, 2)
    assert refreshed is not None
    assert refreshed.current_execution_id == "exec-new"
    assert refreshed.task_status == "RUNNING"
    assert refreshed.consumer_retry_count == 1


def test_increment_consumer_retry_and_release_clears_owner():
    db = build_session()
    create_task(db, task_id=3, status="RUNNING", execution_id="exec-3", consumer_retry_count=1)
    repo = TaskRepo(db)

    assert repo.increment_consumer_retry_and_release(3, "exec-3", "temporary failure") == 1

    refreshed = db.get(PricingTask, 3)
    assert refreshed is not None
    assert refreshed.current_execution_id is None
    assert refreshed.task_status == "RETRYING"
    assert refreshed.consumer_retry_count == 2
    assert refreshed.failure_reason == "temporary failure"


def test_mark_failed_if_owner_does_not_override_cancelled_task():
    db = build_session()
    create_task(db, task_id=4, status="CANCELLED", execution_id="exec-4", consumer_retry_count=0)
    repo = TaskRepo(db)

    assert repo.mark_failed_if_owner(4, "exec-4", "should be ignored") == 0

    refreshed = db.get(PricingTask, 4)
    assert refreshed is not None
    assert refreshed.task_status == "CANCELLED"


def test_mark_failed_if_owner_clears_llm_snapshot():
    db = build_session()
    task = create_task(db, task_id=5, status="RUNNING", execution_id="exec-5", consumer_retry_count=0)
    task.llm_api_key_enc = "cipher"
    task.llm_base_url = "https://persisted.example.com/v1"
    task.llm_model = "persisted-model"
    db.add(task)
    db.commit()
    db.refresh(task)
    repo = TaskRepo(db)

    assert repo.mark_failed_if_owner(5, "exec-5", "boom") == 1

    refreshed = db.get(PricingTask, 5)
    assert refreshed is not None
    assert refreshed.task_status == "FAILED"
    assert refreshed.llm_api_key_enc is None
    assert refreshed.llm_base_url is None
    assert refreshed.llm_model is None


def test_mark_failed_force_clears_llm_snapshot():
    db = build_session()
    task = create_task(db, task_id=6, status="RUNNING", execution_id=None, consumer_retry_count=0)
    task.llm_api_key_enc = "cipher"
    task.llm_base_url = "https://persisted.example.com/v1"
    task.llm_model = "persisted-model"
    db.add(task)
    db.commit()
    db.refresh(task)
    repo = TaskRepo(db)

    assert repo.mark_failed_force(6, "boom") == 1

    refreshed = db.get(PricingTask, 6)
    assert refreshed is not None
    assert refreshed.task_status == "FAILED"
    assert refreshed.llm_api_key_enc is None
    assert refreshed.llm_base_url is None
    assert refreshed.llm_model is None
