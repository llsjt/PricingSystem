from datetime import datetime, timedelta, timezone
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


def create_task(
    db: Session,
    *,
    task_id: int,
    status: str,
    execution_id: str | None = None,
    consumer_retry_count: int = 0,
    retry_count: int = 0,
) -> PricingTask:
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
    assert refreshed.last_heartbeat_at is not None


def test_touch_execution_heartbeat_only_updates_current_owner():
    db = build_session()
    create_task(db, task_id=8, status="RUNNING", execution_id="exec-8")
    repo = TaskRepo(db)

    assert repo.touch_execution_heartbeat(8, "wrong-exec") == 0
    before = db.get(PricingTask, 8).last_heartbeat_at

    assert repo.touch_execution_heartbeat(8, "exec-8") == 1

    refreshed = db.get(PricingTask, 8)
    assert refreshed is not None
    assert refreshed.current_execution_id == "exec-8"
    assert refreshed.task_status == "RUNNING"
    assert refreshed.last_heartbeat_at is not None
    assert refreshed.last_heartbeat_at != before


def test_recover_stale_running_retries_with_owner_fence():
    db = build_session()
    task = create_task(db, task_id=9, status="RUNNING", execution_id="exec-old", retry_count=0)
    stale_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=20)
    task.started_at = stale_time
    task.last_heartbeat_at = stale_time
    db.add(task)
    db.commit()
    repo = TaskRepo(db)

    assert repo.recover_stale_running(
        task.id,
        "wrong-exec",
        stale_before=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5),
        max_retries=2,
        reason="worker heartbeat expired",
    ) is None

    result = repo.recover_stale_running(
        task.id,
        "exec-old",
        stale_before=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5),
        max_retries=2,
        reason="worker heartbeat expired",
    )

    refreshed = db.get(PricingTask, 9)
    assert result == "RETRYING"
    assert refreshed is not None
    assert refreshed.task_status == "RETRYING"
    assert refreshed.retry_count == 1
    assert refreshed.recovery_count == 1
    assert refreshed.current_execution_id is None
    assert refreshed.last_recovered_at is not None
    assert refreshed.failure_reason == "worker heartbeat expired"


def test_recover_stale_running_marks_failed_after_retry_budget():
    db = build_session()
    task = create_task(db, task_id=10, status="RUNNING", execution_id="exec-old", retry_count=2)
    stale_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=20)
    task.started_at = stale_time
    task.last_heartbeat_at = stale_time
    db.add(task)
    db.commit()
    repo = TaskRepo(db)

    result = repo.recover_stale_running(
        task.id,
        "exec-old",
        stale_before=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5),
        max_retries=2,
        reason="worker heartbeat expired",
    )

    refreshed = db.get(PricingTask, 10)
    assert result == "FAILED"
    assert refreshed is not None
    assert refreshed.task_status == "FAILED"
    assert refreshed.retry_count == 2
    assert refreshed.current_execution_id is None
    assert refreshed.completed_at is not None
    assert refreshed.failure_reason == "worker heartbeat expired"


def test_acquire_execution_reclaims_redelivered_task_and_increments_retry_count():
    db = build_session()
    task = create_task(db, task_id=2, status="RUNNING", execution_id="exec-old", consumer_retry_count=0)
    stale_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=20)
    task.started_at = stale_time
    task.last_heartbeat_at = stale_time
    db.add(task)
    db.commit()
    repo = TaskRepo(db)

    assert repo.acquire_execution(
        2,
        "exec-new",
        allow_reclaim=True,
        stale_before=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5),
        max_retry=3,
    ) is True

    refreshed = db.get(PricingTask, 2)
    assert refreshed is not None
    assert refreshed.current_execution_id == "exec-new"
    assert refreshed.task_status == "RUNNING"
    assert refreshed.consumer_retry_count == 1


def test_acquire_execution_does_not_reclaim_live_redelivered_task():
    db = build_session()
    task = create_task(db, task_id=11, status="RUNNING", execution_id="exec-live", consumer_retry_count=0)
    live_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    task.started_at = live_time
    task.last_heartbeat_at = live_time
    db.add(task)
    db.commit()
    repo = TaskRepo(db)

    assert repo.acquire_execution(
        11,
        "exec-new",
        allow_reclaim=True,
        stale_before=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5),
        max_retry=3,
    ) is False

    refreshed = db.get(PricingTask, 11)
    assert refreshed is not None
    assert refreshed.current_execution_id == "exec-live"
    assert refreshed.task_status == "RUNNING"
    assert refreshed.consumer_retry_count == 0


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


def test_mark_retrying_clears_owner_for_next_execution_claim():
    db = build_session()
    create_task(db, task_id=7, status="RUNNING", execution_id="exec-7", consumer_retry_count=0)
    repo = TaskRepo(db)

    task = db.get(PricingTask, 7)
    assert task is not None

    repo.mark_retrying(task, trace_id="trace-7b", failure_reason="agent failed")

    refreshed = db.get(PricingTask, 7)
    assert refreshed is not None
    assert refreshed.task_status == "RETRYING"
    assert refreshed.retry_count == 1
    assert refreshed.current_execution_id is None
    assert refreshed.failure_reason == "agent failed"


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
