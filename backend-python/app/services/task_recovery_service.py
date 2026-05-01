"""Automatic recovery for orphaned pricing task executions."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repos.task_repo import TaskRepo
from app.services.dispatch_publisher_service import get_dispatch_publisher_service

logger = logging.getLogger(__name__)


class TaskPublisher(Protocol):
    async def publish_task(self, task_id: int, trace_id: str | None) -> None:
        ...


@dataclass
class RecoveryResult:
    scanned: int = 0
    requeued: int = 0
    failed: int = 0
    republished: int = 0
    skipped: int = 0
    publish_failed: int = 0


class TaskRecoveryService:
    def __init__(self, db: Session, publisher: TaskPublisher | None = None):
        self.db = db
        self.repo = TaskRepo(db)
        self.publisher = publisher or get_dispatch_publisher_service()

    def recover_once(
        self,
        *,
        lease_timeout_seconds: int,
        max_retries: int,
        batch_size: int,
        dispatch_republish_seconds: int = 120,
    ) -> RecoveryResult:
        return asyncio.run(
            self.recover_once_async(
                lease_timeout_seconds=lease_timeout_seconds,
                max_retries=max_retries,
                batch_size=batch_size,
                dispatch_republish_seconds=dispatch_republish_seconds,
            )
        )

    async def recover_once_async(
        self,
        *,
        lease_timeout_seconds: int,
        max_retries: int,
        batch_size: int,
        dispatch_republish_seconds: int = 120,
    ) -> RecoveryResult:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        stale_before = now - timedelta(seconds=max(int(lease_timeout_seconds or 1), 1))
        republish_before = now - timedelta(seconds=max(int(dispatch_republish_seconds or 1), 1))
        result = RecoveryResult()
        touched_task_ids: set[int] = set()

        for task in self.repo.list_stale_running(stale_before, limit=batch_size):
            result.scanned += 1
            touched_task_ids.add(int(task.id))
            execution_id = str(task.current_execution_id or "")
            if not execution_id:
                result.skipped += 1
                continue

            status = self.repo.recover_stale_running(
                task.id,
                execution_id,
                stale_before=stale_before,
                max_retries=max_retries,
                reason="worker heartbeat expired",
            )
            if status == "FAILED":
                result.failed += 1
                logger.warning("Marked stale RUNNING task failed, taskId=%s", task.id)
                continue
            if status == "RETRYING":
                result.requeued += 1
                if await self._publish(task.id, task.trace_id):
                    result.republished += 1
                else:
                    result.publish_failed += 1
                continue
            result.skipped += 1

        remaining = max(int(batch_size or 1) - result.scanned, 0)
        if remaining:
            for task in self.repo.list_stale_dispatchable(republish_before, limit=remaining):
                if int(task.id) in touched_task_ids:
                    continue
                if await self._publish(task.id, task.trace_id):
                    result.republished += 1
                else:
                    result.publish_failed += 1

        return result

    async def _publish(self, task_id: int, trace_id: str | None) -> bool:
        try:
            await self.publisher.publish_task(task_id, trace_id)
            logger.warning("Published recovery dispatch for taskId=%s", task_id)
            return True
        except Exception:
            logger.exception("Publish recovery dispatch failed, taskId=%s", task_id)
            return False


class TaskRecoveryLoop:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._started = False

    async def start(self) -> None:
        settings = get_settings()
        if self._started or not settings.recovery_enabled:
            return
        self._started = True
        self._task = asyncio.create_task(self._run())
        await asyncio.sleep(0)

    async def stop(self) -> None:
        self._started = False
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    async def _run(self) -> None:
        settings = get_settings()
        interval = max(int(settings.recovery_scan_interval_seconds or 1), 1)
        while self._started:
            db = SessionLocal()
            try:
                result = await TaskRecoveryService(db).recover_once_async(
                    lease_timeout_seconds=settings.running_lease_timeout_seconds,
                    max_retries=settings.agent_max_retries,
                    batch_size=settings.recovery_batch_size,
                    dispatch_republish_seconds=settings.dispatch_republish_seconds,
                )
                if result.scanned or result.republished or result.failed or result.publish_failed:
                    logger.warning("Task recovery scan result: %s", result)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Task recovery scan failed")
            finally:
                db.close()
            await asyncio.sleep(interval)


_task_recovery_loop = TaskRecoveryLoop()


def get_task_recovery_loop() -> TaskRecoveryLoop:
    return _task_recovery_loop
