import asyncio
import logging

from app.core.config import get_settings
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


class TaskQueueService:
    def __init__(self, worker_count: int | None = None, maxsize: int | None = None) -> None:
        settings = get_settings()
        self._worker_count = max(worker_count or settings.agent_worker_concurrency, 1)
        self._poll_interval_seconds = max(settings.agent_poll_interval_ms, 100) / 1000
        self._configured_maxsize = max(maxsize or settings.agent_queue_maxsize, 1)
        self._workers: list[asyncio.Task] = []
        self._active_task_ids: set[int] = set()
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        self._workers = [asyncio.create_task(self._worker_loop(index + 1)) for index in range(self._worker_count)]
        self._started = True
        logger.info("Started %s db-backed task queue workers", self._worker_count)

    async def stop(self) -> None:
        if not self._started:
            return
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        self._started = False

    def enqueue_nowait(self, request) -> int:
        return self.queue_size()

    def enqueue(self, request) -> bool:
        return True

    def mark_running(self, task_id: int) -> None:
        self._active_task_ids.add(int(task_id))

    def mark_finished(self, task_id: int) -> None:
        self._active_task_ids.discard(int(task_id))

    def queue_size(self) -> int:
        from app.repos.task_repo import TaskRepo

        db = SessionLocal()
        try:
            return TaskRepo(db).count_dispatchable()
        finally:
            db.close()

    def can_accept(self) -> bool:
        return self.queue_size() < self._configured_maxsize

    def snapshot(self) -> dict[str, int | bool]:
        return {
            "queueSize": self.queue_size(),
            "workerCount": self._worker_count,
            "activeTaskCount": len(self._active_task_ids),
            "started": self._started,
            "maxsize": self._configured_maxsize,
        }

    def recover_pending_tasks(self) -> int:
        from app.services.dispatch_service import DispatchService

        db = SessionLocal()
        try:
            settings = get_settings()
            return DispatchService(db).recover_pending_tasks(self, max_retries=settings.agent_max_retries)
        finally:
            db.close()

    async def _worker_loop(self, worker_id: int) -> None:
        while True:
            try:
                request = await asyncio.to_thread(self._claim_next_request)
                if request is None:
                    await asyncio.sleep(self._poll_interval_seconds)
                    continue

                task_id = self._extract_task_id(request)
                if task_id is not None:
                    self.mark_running(task_id)
                try:
                    await asyncio.to_thread(self._run_request, request, worker_id)
                except Exception as exc:
                    logger.exception("Queue worker %s crashed while processing task", worker_id)
                    self._handle_worker_failure(request, exc)
                finally:
                    if task_id is not None:
                        self.mark_finished(task_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Queue worker %s failed in polling loop", worker_id)
                await asyncio.sleep(self._poll_interval_seconds)

    def _claim_next_request(self):
        from app.repos.task_repo import TaskRepo
        from app.services.dispatch_service import DispatchService

        db = SessionLocal()
        try:
            repo = TaskRepo(db)
            task = repo.claim_next_dispatchable()
            if task is None:
                return None
            return DispatchService(db).build_dispatch_request(task)
        finally:
            db.close()

    def _run_request(self, request, worker_id: int) -> None:
        from app.services.dispatch_service import DispatchService

        db = SessionLocal()
        try:
            DispatchService(db).execute_queued(request, worker_id=worker_id)
        finally:
            db.close()

    def _handle_worker_failure(self, request, exc: Exception) -> None:
        from app.services.dispatch_service import DispatchService

        db = SessionLocal()
        try:
            settings = get_settings()
            DispatchService(db).handle_worker_failure(request, str(exc), max_retries=settings.agent_max_retries)
        finally:
            db.close()

    @staticmethod
    def _extract_task_id(request) -> int | None:
        if request is None:
            return None
        if isinstance(request, dict):
            task_id = request.get("task_id")
        else:
            task_id = getattr(request, "task_id", None)
        if task_id is None:
            return None
        return int(task_id)


_task_queue_service = TaskQueueService()


def get_task_queue_service() -> TaskQueueService:
    return _task_queue_service
