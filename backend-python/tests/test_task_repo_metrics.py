from datetime import datetime, timedelta
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
    created_at: datetime,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> PricingTask:
    task = PricingTask(
        id=task_id,
        task_code=f"TASK-{task_id}",
        shop_id=1,
        product_id=task_id,
        current_price=Decimal("19.90"),
        baseline_profit=Decimal("10.00"),
        task_status=status,
        strategy_goal="MAX_PROFIT",
        constraint_text="",
        trace_id=f"trace-{task_id}",
        retry_count=0,
        created_at=created_at,
        started_at=started_at,
        completed_at=completed_at,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def test_metrics_snapshot_counts_durations_and_stale_running_tasks():
    db = build_session()
    now = datetime(2026, 4, 8, 13, 0, 0)
    create_task(db, task_id=1, status="QUEUED", created_at=now - timedelta(minutes=3))
    create_task(db, task_id=2, status="RUNNING", created_at=now - timedelta(minutes=20), started_at=now - timedelta(minutes=20))
    create_task(db, task_id=3, status="RETRYING", created_at=now - timedelta(minutes=5), started_at=now - timedelta(minutes=5))
    create_task(
        db,
        task_id=4,
        status="COMPLETED",
        created_at=now - timedelta(minutes=15),
        started_at=now - timedelta(minutes=14),
        completed_at=now - timedelta(minutes=10),
    )
    create_task(
        db,
        task_id=5,
        status="FAILED",
        created_at=now - timedelta(minutes=8),
        started_at=now - timedelta(minutes=7),
        completed_at=now - timedelta(minutes=5),
    )
    create_task(
        db,
        task_id=6,
        status="MANUAL_REVIEW",
        created_at=now - timedelta(minutes=6),
        started_at=now - timedelta(minutes=6),
        completed_at=now - timedelta(minutes=4),
    )
    create_task(
        db,
        task_id=7,
        status="CANCELLED",
        created_at=now - timedelta(minutes=4),
        started_at=now - timedelta(minutes=4),
        completed_at=now - timedelta(minutes=3),
    )

    snapshot = TaskRepo(db).metrics_snapshot(now=now, stale_after_seconds=900)

    assert snapshot["total"] == 7
    assert snapshot["queued"] == 1
    assert snapshot["running"] == 1
    assert snapshot["retrying"] == 1
    assert snapshot["queueDepth"] == 2
    assert snapshot["activeExecutions"] == 1
    assert snapshot["manualReview"] == 1
    assert snapshot["failed"] == 1
    assert snapshot["cancelled"] == 1
    assert snapshot["staleRunningTasks"] == 1
    assert snapshot["avgDurationSeconds"] == 135.0
    assert snapshot["maxDurationSeconds"] == 240.0
