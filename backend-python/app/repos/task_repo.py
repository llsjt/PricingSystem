from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.pricing_task import PricingTask
from app.utils.math_utils import money


class TaskRepo:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, task_id: int) -> PricingTask | None:
        return self.db.get(PricingTask, task_id)

    def list_recoverable(self) -> list[PricingTask]:
        stmt = (
            select(PricingTask)
            .where(PricingTask.task_status.in_(("QUEUED", "RETRYING", "RUNNING")))
            .order_by(PricingTask.id.asc())
        )
        return list(self.db.scalars(stmt).all())

    def count_dispatchable(self) -> int:
        stmt = select(func.count()).select_from(PricingTask).where(PricingTask.task_status.in_(("QUEUED", "RETRYING")))
        return int(self.db.scalar(stmt) or 0)

    def claim_next_dispatchable(self) -> PricingTask | None:
        for _ in range(8):
            stmt = (
                select(PricingTask)
                .where(PricingTask.task_status.in_(("QUEUED", "RETRYING")))
                .order_by(PricingTask.created_at.asc(), PricingTask.id.asc())
                .limit(1)
            )
            candidate = self.db.scalars(stmt).first()
            if candidate is None:
                return None

            previous_status = str(candidate.task_status or "").upper()
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            updated = (
                self.db.query(PricingTask)
                .filter(PricingTask.id == candidate.id, PricingTask.task_status == previous_status)
                .update(
                    {
                        PricingTask.task_status: "RUNNING",
                        PricingTask.started_at: now,
                        PricingTask.completed_at: None,
                    },
                    synchronize_session=False,
                )
            )
            if updated == 1:
                self.db.commit()
                return self.get_by_id(candidate.id)
            self.db.rollback()

        return None

    def update_status(
        self,
        task: PricingTask,
        status: str,
        *,
        failure_reason: str | None = None,
        clear_failure_reason: bool = False,
    ) -> PricingTask:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        task.task_status = status
        if clear_failure_reason:
            task.failure_reason = None
        elif failure_reason is not None:
            task.failure_reason = failure_reason[:255]

        if status in {"RUNNING"}:
            task.started_at = now
            task.completed_at = None
        elif status in {"FAILED", "CANCELLED", "COMPLETED", "MANUAL_REVIEW"}:
            task.completed_at = now

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def mark_queued(self, task: PricingTask, trace_id: str | None = None) -> PricingTask:
        task.task_status = "QUEUED"
        task.trace_id = trace_id or task.trace_id
        task.failure_reason = None
        task.started_at = None
        task.completed_at = None
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def mark_retrying(
        self,
        task: PricingTask,
        trace_id: str | None = None,
        failure_reason: str | None = None,
    ) -> PricingTask:
        task.task_status = "RETRYING"
        task.retry_count = int(task.retry_count or 0) + 1
        task.trace_id = trace_id or task.trace_id
        task.failure_reason = failure_reason[:255] if failure_reason else None
        task.started_at = None
        task.completed_at = None
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def mark_manual_review(self, task: PricingTask, failure_reason: str | None = None) -> PricingTask:
        return self.update_status(task, "MANUAL_REVIEW", failure_reason=failure_reason)

    def mark_cancelled(self, task: PricingTask, failure_reason: str | None = None) -> PricingTask:
        return self.update_status(task, "CANCELLED", failure_reason=failure_reason or "任务已取消")

    def set_suggested_range(self, task: PricingTask, min_price: Decimal, max_price: Decimal) -> PricingTask:
        task.suggested_min_price = money(min_price)
        task.suggested_max_price = money(max_price)
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def find_by_code(self, task_code: str) -> PricingTask | None:
        stmt = select(PricingTask).where(PricingTask.task_code == task_code).limit(1)
        return self.db.scalars(stmt).first()

    def metrics_snapshot(self, now: datetime | None = None, stale_after_seconds: int = 900) -> dict[str, int | float | str | None]:
        current = now or datetime.now(timezone.utc).replace(tzinfo=None)
        stale_threshold = current - timedelta(seconds=max(stale_after_seconds, 1))
        tasks = list(self.db.scalars(select(PricingTask)).all())

        total = len(tasks)
        queued = retrying = running = completed = manual_review = failed = cancelled = stale_running = 0
        duration_sum = 0.0
        duration_max = 0.0
        duration_samples = 0
        latest_created_at: datetime | None = None

        for task in tasks:
            status = str(task.task_status or "").upper()
            if task.created_at and (latest_created_at is None or task.created_at > latest_created_at):
                latest_created_at = task.created_at

            if status == "QUEUED":
                queued += 1
            elif status == "RETRYING":
                retrying += 1
            elif status == "RUNNING":
                running += 1
            elif status == "COMPLETED":
                completed += 1
            elif status == "MANUAL_REVIEW":
                manual_review += 1
            elif status == "FAILED":
                failed += 1
            elif status == "CANCELLED":
                cancelled += 1

            if status in {"RUNNING", "RETRYING"} and task.started_at and task.started_at <= stale_threshold:
                stale_running += 1

            if status in {"COMPLETED", "MANUAL_REVIEW", "FAILED", "CANCELLED"} and task.started_at and task.completed_at:
                duration_seconds = max((task.completed_at - task.started_at).total_seconds(), 0.0)
                duration_samples += 1
                duration_sum += duration_seconds
                duration_max = max(duration_max, duration_seconds)

        return {
            "total": total,
            "queued": queued,
            "retrying": retrying,
            "running": running,
            "queueDepth": queued + retrying,
            "activeExecutions": running,
            "completed": completed,
            "manualReview": manual_review,
            "failed": failed,
            "cancelled": cancelled,
            "staleRunningTasks": stale_running,
            "avgDurationSeconds": round(duration_sum / duration_samples, 2) if duration_samples else 0.0,
            "maxDurationSeconds": round(duration_max, 2),
            "latestTaskCreatedAt": latest_created_at.isoformat() if latest_created_at else None,
        }
