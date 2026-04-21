"""RabbitMQ Worker 服务，负责消费异步任务并驱动本地执行。"""

import asyncio
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repos.task_repo import TaskRepo
from app.services.dispatch_service import DispatchService

logger = logging.getLogger(__name__)

TERMINAL_STATES = {"COMPLETED", "FAILED", "CANCELLED", "MANUAL_REVIEW"}
FAILURE_REASON_MAX_LEN = 255


class RecoverableError(Exception):
    """可恢复的 Worker 异常，出现后应把消息重新放回队列。"""


def _truncate(msg: str | None, limit: int = FAILURE_REASON_MAX_LEN) -> str:
    if msg is None:
        return ""
    return msg if len(msg) <= limit else msg[: limit - 3] + "..."


class _NoopProgressService:
    async def publish(self, event_type: str, task_id: int, execution_id: str | None, payload: dict[str, Any]) -> None:
        return None


class _DispatchRunner:
    async def run_task(self, task_id: int, execution_id: str) -> None:
        db = SessionLocal()
        try:
            service = DispatchService(db)
            await asyncio.to_thread(service.execute_queued_by_task_id, task_id, execution_id)
        finally:
            db.close()


class RabbitMqWorkerService:
    def __init__(
        self,
        *,
        repo: TaskRepo | None = None,
        dispatch_service: Any | None = None,
        progress_service: Any | None = None,
        settings=None,
        sleep_func: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.repo = repo
        self.dispatch_service = dispatch_service or _DispatchRunner()
        self.progress_service = progress_service or _NoopProgressService()
        self.sleep_func = sleep_func or asyncio.sleep
        self._started = False
        self._ready = False
        self._runner_task: asyncio.Task | None = None
        self._connection = None
        self._channel = None
        self._queue = None

    @property
    def ready(self) -> bool:
        return self._ready

    def snapshot(self) -> dict[str, int | bool]:
        return {
            "started": self._started,
            "ready": self._ready,
            "prefetch": int(self.settings.rabbitmq_prefetch),
            "maxRetry": int(self.settings.worker_max_retry),
        }

    async def start(self) -> None:
        if self.repo is not None:
            self._started = True
            self._ready = True
            return
        if self._runner_task and not self._runner_task.done():
            return
        self._started = True
        self._runner_task = asyncio.create_task(self._run())
        await asyncio.sleep(0)

    async def stop(self) -> None:
        self._started = False
        self._ready = False
        if self._runner_task is not None:
            self._runner_task.cancel()
            await asyncio.gather(self._runner_task, return_exceptions=True)
            self._runner_task = None
        if self._channel is not None:
            await self._channel.close()
            self._channel = None
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def _run(self) -> None:
        if self.repo is not None:
            return
        import aio_pika

        backoff = 1
        # 常驻连接 RabbitMQ；一旦连接失败就按退避策略重连，直到服务被显式停止。
        while self._started:
            try:
                self._connection = await aio_pika.connect_robust(
                    host=self.settings.rabbitmq_host,
                    port=self.settings.rabbitmq_port,
                    login=self.settings.rabbitmq_username,
                    password=self.settings.rabbitmq_password,
                    virtualhost=self.settings.rabbitmq_vhost,
                )
                self._channel = await self._connection.channel()
                await self._channel.set_qos(prefetch_count=int(self.settings.rabbitmq_prefetch))
                exchange = await self._channel.declare_exchange(
                    self.settings.task_dispatch_exchange,
                    aio_pika.ExchangeType.DIRECT,
                    durable=True,
                )
                self._queue = await self._channel.declare_queue(self.settings.task_dispatch_queue, durable=True)
                await self._queue.bind(exchange, routing_key=self.settings.task_dispatch_routing_key)
                await self._queue.consume(self.on_message)
                self._ready = True
                await asyncio.Future()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("RabbitMQ worker connection failed")
                self._ready = False
                await self.sleep_func(backoff)
                backoff = min(backoff * 2, 30)

    async def on_message(self, message: Any) -> None:
        """消费单条派发消息，并完成抢占执行权、执行任务、确认或重入队列。"""
        try:
            payload = json.loads(message.body)
            task_id = int(payload["taskId"])
        except Exception:
            await message.ack()
            return

        repo = self.repo or TaskRepo(SessionLocal())
        owns_repo_session = self.repo is None
        try:
            task = await asyncio.to_thread(repo.get_by_id, task_id)
            if task is None or str(task.task_status or "").upper() in TERMINAL_STATES:
                await message.ack()
                return

            retry_exhausted = int(task.consumer_retry_count or 0) >= int(self.settings.worker_max_retry)
            has_owner = bool(task.current_execution_id)
            if retry_exhausted:
                if (not has_owner) or bool(getattr(message, "redelivered", False)):
                    await asyncio.to_thread(repo.mark_failed_force, task_id, _truncate("超过最大消费重试次数"))
                    await self.progress_service.publish("TASK_FAILED", task_id, None, {"reason": "超过最大消费重试次数"})
                await message.ack()
                return

            execution_id = str(uuid.uuid4())
            # 只有成功抢到 current_execution_id 的 Worker 才能继续执行，避免同一任务被重复消费。
            acquired = await asyncio.to_thread(
                repo.acquire_execution,
                task_id,
                execution_id,
                allow_reclaim=bool(getattr(message, "redelivered", False)),
                max_retry=int(self.settings.worker_max_retry),
            )
            if not acquired:
                await message.ack()
                return

            try:
                await self.progress_service.publish("TASK_STARTED", task_id, execution_id, {})
                await self.dispatch_service.run_task(task_id, execution_id)
                await message.ack()
            except RecoverableError as exc:
                # 可恢复错误走“释放执行权 + 增加消费重试次数 + 重新入队”这条路径。
                await asyncio.to_thread(
                    repo.increment_consumer_retry_and_release,
                    task_id,
                    execution_id,
                    _truncate(str(exc)),
                )
                retry_count = int((task.consumer_retry_count or 0) + 1)
                backoff = min(2 ** retry_count, int(self.settings.worker_retry_backoff_max_seconds))
                await self.sleep_func(backoff)
                await message.nack(requeue=True)
            except Exception as exc:
                await asyncio.to_thread(
                    repo.mark_failed_if_owner,
                    task_id,
                    execution_id,
                    _truncate(str(exc)),
                )
                await self.progress_service.publish("TASK_FAILED", task_id, execution_id, {"reason": _truncate(str(exc))})
                await message.ack()
        finally:
            if owns_repo_session:
                repo.db.close()


_rabbitmq_worker_service = RabbitMqWorkerService()


def get_rabbitmq_worker_service() -> RabbitMqWorkerService:
    return _rabbitmq_worker_service
