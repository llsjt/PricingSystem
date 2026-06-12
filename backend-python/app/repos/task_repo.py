"""任务仓储模块，封装定价任务状态流转与查询操作。"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.models.pricing_task import PricingTask
from app.utils.math_utils import money


TERMINAL_STATES = ("COMPLETED", "FAILED", "CANCELLED", "MANUAL_REVIEW")
FINALIZABLE_STATES = ("RUNNING", "QUEUED", "RETRYING")


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
                        PricingTask.last_heartbeat_at: now,
                    },
                    synchronize_session=False,
                )
            )
            if updated == 1:
                self.db.commit()
                return self.get_by_id(candidate.id)
            self.db.rollback()

        return None

    def acquire_execution(
        self,
        task_id: int,
        execution_id: str,
        *,
        allow_reclaim: bool,
        stale_before: datetime | None = None,
        max_retry: int,
    ) -> bool:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        stale_threshold = stale_before or now
        filters = [
            PricingTask.id == int(task_id),
            PricingTask.task_status.notin_(TERMINAL_STATES),
            PricingTask.consumer_retry_count < int(max_retry),
        ]
        if allow_reclaim:
            filters.append(
                or_(
                    PricingTask.current_execution_id.is_(None),
                    and_(
                        PricingTask.current_execution_id.is_not(None),
                        self._stale_lease_filter(stale_threshold),
                    ),
                )
            )
        else:
            filters.append(PricingTask.current_execution_id.is_(None))

        updated = (
            self.db.query(PricingTask)
            .filter(*filters)
            .update(
                {
                    PricingTask.current_execution_id: execution_id,
                    PricingTask.task_status: "RUNNING",
                    PricingTask.started_at: now,
                    PricingTask.completed_at: None,
                    PricingTask.last_heartbeat_at: now,
                    PricingTask.failure_reason: None,
                    PricingTask.consumer_retry_count: case(
                        (PricingTask.current_execution_id.is_(None), PricingTask.consumer_retry_count),
                        else_=PricingTask.consumer_retry_count + 1,
                    ),
                },
                synchronize_session=False,
            )
        )
        self.db.commit()
        return updated == 1

    def touch_execution_heartbeat(self, task_id: int, execution_id: str) -> int:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        updated = (
            self.db.query(PricingTask)
            .filter(
                PricingTask.id == int(task_id),
                PricingTask.current_execution_id == execution_id,
                PricingTask.task_status == "RUNNING",
            )
            .update({PricingTask.last_heartbeat_at: now}, synchronize_session=False)
        )
        self.db.commit()
        return int(updated or 0)

    def list_stale_running(self, stale_before: datetime, limit: int = 50) -> list[PricingTask]:
        stmt = (
            select(PricingTask)
            .where(
                PricingTask.task_status == "RUNNING",
                PricingTask.completed_at.is_(None),
                PricingTask.current_execution_id.is_not(None),
                self._stale_lease_filter(stale_before),
            )
            .order_by(PricingTask.last_heartbeat_at.asc(), PricingTask.started_at.asc(), PricingTask.id.asc())
            .limit(max(int(limit or 1), 1))
        )
        return list(self.db.scalars(stmt).all())

    def list_stale_dispatchable(self, stale_before: datetime, limit: int = 50) -> list[PricingTask]:
        stmt = (
            select(PricingTask)
            .where(
                PricingTask.task_status.in_(("QUEUED", "RETRYING")),
                PricingTask.current_execution_id.is_(None),
                PricingTask.updated_at <= stale_before,
            )
            .order_by(PricingTask.updated_at.asc(), PricingTask.id.asc())
            .limit(max(int(limit or 1), 1))
        )
        return list(self.db.scalars(stmt).all())

    def recover_stale_running(
        self,
        task_id: int,
        execution_id: str,
        *,
        stale_before: datetime,
        max_retries: int,
        reason: str | None,
    ) -> str | None:
        filters = [
            PricingTask.id == int(task_id),
            PricingTask.current_execution_id == execution_id,
            PricingTask.task_status == "RUNNING",
            PricingTask.completed_at.is_(None),
            self._stale_lease_filter(stale_before),
        ]
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        safe_reason = (reason or "worker heartbeat expired")[:255]

        failed = (
            self.db.query(PricingTask)
            .filter(*filters, PricingTask.retry_count >= max(int(max_retries), 0))
            .update(
                {
                    PricingTask.task_status: "FAILED",
                    PricingTask.current_execution_id: None,
                    PricingTask.last_heartbeat_at: None,
                    PricingTask.failure_reason: safe_reason,
                    PricingTask.llm_api_key_enc: None,
                    PricingTask.llm_base_url: None,
                    PricingTask.llm_model: None,
                    PricingTask.completed_at: now,
                    PricingTask.recovery_count: PricingTask.recovery_count + 1,
                    PricingTask.last_recovered_at: now,
                },
                synchronize_session=False,
            )
        )
        if failed:
            self.db.commit()
            return "FAILED"

        requeued = (
            self.db.query(PricingTask)
            .filter(*filters, PricingTask.retry_count < max(int(max_retries), 0))
            .update(
                {
                    PricingTask.task_status: "RETRYING",
                    PricingTask.retry_count: PricingTask.retry_count + 1,
                    PricingTask.current_execution_id: None,
                    PricingTask.last_heartbeat_at: None,
                    PricingTask.failure_reason: safe_reason,
                    PricingTask.started_at: None,
                    PricingTask.completed_at: None,
                    PricingTask.recovery_count: PricingTask.recovery_count + 1,
                    PricingTask.last_recovered_at: now,
                },
                synchronize_session=False,
            )
        )
        self.db.commit()
        if requeued:
            return "RETRYING"
        return None

    def increment_consumer_retry_and_release(self, task_id: int, execution_id: str, reason: str | None) -> int:
        updated = (
            self.db.query(PricingTask)
            .filter(
                PricingTask.id == int(task_id),
                PricingTask.current_execution_id == execution_id,
                PricingTask.task_status.notin_(TERMINAL_STATES),
            )
            .update(
                {
                    PricingTask.consumer_retry_count: PricingTask.consumer_retry_count + 1,
                    PricingTask.current_execution_id: None,
                    PricingTask.last_heartbeat_at: None,
                    PricingTask.task_status: "RETRYING",
                    PricingTask.started_at: None,
                    PricingTask.completed_at: None,
                    PricingTask.failure_reason: (reason or "")[:255] if reason else None,
                },
                synchronize_session=False,
            )
        )
        self.db.commit()
        return int(updated or 0)

    def mark_failed_if_owner(self, task_id: int, execution_id: str, reason: str | None) -> int:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        updated = (
            self.db.query(PricingTask)
            .filter(
                PricingTask.id == int(task_id),
                PricingTask.current_execution_id == execution_id,
                PricingTask.task_status.notin_(TERMINAL_STATES),
            )
            .update(
                {
                    PricingTask.task_status: "FAILED",
                    PricingTask.current_execution_id: None,
                    PricingTask.last_heartbeat_at: None,
                    PricingTask.failure_reason: (reason or "")[:255] if reason else None,
                    PricingTask.llm_api_key_enc: None,
                    PricingTask.llm_base_url: None,
                    PricingTask.llm_model: None,
                    PricingTask.completed_at: now,
                },
                synchronize_session=False,
            )
        )
        self.db.commit()
        return int(updated or 0)

    def mark_failed_force(self, task_id: int, reason: str | None) -> int:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        updated = (
            self.db.query(PricingTask)
            .filter(
                PricingTask.id == int(task_id),
                PricingTask.task_status.notin_(TERMINAL_STATES),
            )
            .update(
                {
                    PricingTask.task_status: "FAILED",
                    PricingTask.current_execution_id: None,
                    PricingTask.last_heartbeat_at: None,
                    PricingTask.failure_reason: (reason or "")[:255] if reason else None,
                    PricingTask.llm_api_key_enc: None,
                    PricingTask.llm_base_url: None,
                    PricingTask.llm_model: None,
                    PricingTask.completed_at: now,
                },
                synchronize_session=False,
            )
        )
        self.db.commit()
        return int(updated or 0)

    def update_status(
        self,
        task: PricingTask,
        status: str,
        *,
        failure_reason: str | None = None,
        clear_failure_reason: bool = False,
        execution_id: str | None = None,
    ) -> PricingTask:
        current_status = str(task.task_status or "").upper()
        next_status = str(status or "").upper()
        if current_status in TERMINAL_STATES and current_status != next_status:
            return task
        if execution_id and not self._can_write(task, execution_id):
            return task
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        task.task_status = status
        if clear_failure_reason:
            task.failure_reason = None
        elif failure_reason is not None:
            task.failure_reason = failure_reason[:255]

        if status in {"RUNNING"}:
            task.started_at = now
            task.completed_at = None
            task.last_heartbeat_at = now
        elif status in {"FAILED", "CANCELLED", "COMPLETED", "MANUAL_REVIEW"}:
            task.completed_at = now
            task.current_execution_id = None
            task.last_heartbeat_at = None

        if status in {"FAILED", "CANCELLED", "COMPLETED", "MANUAL_REVIEW"}:
            task.llm_api_key_enc = None
            task.llm_base_url = None
            task.llm_model = None

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
        task.current_execution_id = None
        task.last_heartbeat_at = None
        task.trace_id = trace_id or task.trace_id
        task.failure_reason = failure_reason[:255] if failure_reason else None
        task.started_at = None
        task.completed_at = None
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def mark_retrying_if_owner(
        self,
        task_id: int,
        execution_id: str,
        *,
        trace_id: str | None = None,
        failure_reason: str | None = None,
    ) -> int:
        updated_values = {
            PricingTask.task_status: "RETRYING",
            PricingTask.retry_count: PricingTask.retry_count + 1,
            PricingTask.current_execution_id: None,
            PricingTask.last_heartbeat_at: None,
            PricingTask.failure_reason: failure_reason[:255] if failure_reason else None,
            PricingTask.started_at: None,
            PricingTask.completed_at: None,
        }
        if trace_id:
            updated_values[PricingTask.trace_id] = trace_id
        updated = (
            self.db.query(PricingTask)
            .filter(
                PricingTask.id == int(task_id),
                PricingTask.current_execution_id == execution_id,
                PricingTask.task_status.notin_(TERMINAL_STATES),
            )
            .update(updated_values, synchronize_session=False)
        )
        self.db.commit()
        return int(updated or 0)

    def mark_manual_review(self, task: PricingTask, failure_reason: str | None = None) -> PricingTask:
        return self.update_status(task, "MANUAL_REVIEW", failure_reason=failure_reason)

    def mark_cancelled(self, task: PricingTask, failure_reason: str | None = None) -> PricingTask:
        return self.update_status(task, "CANCELLED", failure_reason=failure_reason or "任务已取消")

    def set_suggested_range(self, task: PricingTask, min_price: Decimal, max_price: Decimal, execution_id: str | None = None) -> PricingTask:
        if execution_id and not self._can_write(task, execution_id):
            return task
        task.suggested_min_price = money(min_price)
        task.suggested_max_price = money(max_price)
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def finalize_manual_review_if_owner(
        self,
        *,
        task_id: int,
        execution_id: str,
        suggested_min_price: Decimal,
        suggested_max_price: Decimal,
        failure_reason: str | None = None,
    ) -> int:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        values = {
            PricingTask.suggested_min_price: money(suggested_min_price),
            PricingTask.suggested_max_price: money(suggested_max_price),
            PricingTask.task_status: "MANUAL_REVIEW",
            PricingTask.completed_at: now,
            PricingTask.current_execution_id: None,
            PricingTask.last_heartbeat_at: None,
            PricingTask.llm_api_key_enc: None,
            PricingTask.llm_base_url: None,
            PricingTask.llm_model: None,
        }
        if failure_reason is not None:
            values[PricingTask.failure_reason] = failure_reason[:255]
        else:
            values[PricingTask.failure_reason] = None

        updated = (
            self.db.query(PricingTask)
            .filter(
                PricingTask.id == int(task_id),
                PricingTask.current_execution_id == execution_id,
                PricingTask.task_status.in_(FINALIZABLE_STATES),
            )
            .update(values, synchronize_session=False)
        )
        return int(updated or 0)

    def find_by_code(self, task_code: str) -> PricingTask | None:
        stmt = select(PricingTask).where(PricingTask.task_code == task_code).limit(1)
        return self.db.scalars(stmt).first()

    @staticmethod
    def _can_write(task: PricingTask, execution_id: str) -> bool:
        status = str(task.task_status or "").upper()
        if status in TERMINAL_STATES:
            return False
        return str(task.current_execution_id or "") == execution_id

    def metrics_snapshot(self, now: datetime | None = None, stale_after_seconds: int = 900) -> dict[str, int | float | str | None]:
        current = now or datetime.now(timezone.utc).replace(tzinfo=None)
        stale_threshold = current - timedelta(seconds=max(stale_after_seconds, 1))
        tasks = list(self.db.scalars(select(PricingTask)).all())

        total = len(tasks)
        queued = retrying = running = completed = manual_review = failed = cancelled = stale_running = 0
        consumer_retry_count = 0
        duration_sum = 0.0
        duration_max = 0.0
        duration_samples = 0
        latest_created_at: datetime | None = None

        for task in tasks:
            status = str(task.task_status or "").upper()
            consumer_retry_count += int(task.consumer_retry_count or 0)
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

            lease_time = task.last_heartbeat_at or task.started_at
            if status == "RUNNING" and lease_time and lease_time <= stale_threshold:
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
            "consumerRetryCount": consumer_retry_count,
            "avgDurationSeconds": round(duration_sum / duration_samples, 2) if duration_samples else 0.0,
            "maxDurationSeconds": round(duration_max, 2),
            "latestTaskCreatedAt": latest_created_at.isoformat() if latest_created_at else None,
        }

    @staticmethod
    def _stale_lease_filter(stale_before: datetime):
        return or_(
            PricingTask.last_heartbeat_at <= stale_before,
            and_(PricingTask.last_heartbeat_at.is_(None), PricingTask.started_at <= stale_before),
            and_(
                PricingTask.last_heartbeat_at.is_(None),
                PricingTask.started_at.is_(None),
                PricingTask.updated_at <= stale_before,
            ),
        )
