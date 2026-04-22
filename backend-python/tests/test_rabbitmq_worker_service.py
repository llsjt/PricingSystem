import asyncio
import json
import sys
from types import SimpleNamespace

from app.services.rabbitmq_worker_service import RabbitMqWorkerService, RecoverableError, _truncate


class FakeMessage:
    def __init__(self, body: bytes, *, redelivered: bool = False):
        self.body = body
        self.redelivered = redelivered
        self.acked = 0
        self.nacked: list[bool] = []

    async def ack(self) -> None:
        self.acked += 1

    async def nack(self, requeue: bool = False) -> None:
        self.nacked.append(bool(requeue))


class FakeTask:
    def __init__(self, *, task_status: str, consumer_retry_count: int = 0, current_execution_id: str | None = None):
        self.task_status = task_status
        self.consumer_retry_count = consumer_retry_count
        self.current_execution_id = current_execution_id


class FakeRepo:
    def __init__(self, task):
        self.task = task
        self.calls: list[tuple] = []

    def get_by_id(self, task_id: int):
        self.calls.append(("get_by_id", task_id))
        return self.task

    def acquire_execution(self, task_id: int, execution_id: str, *, allow_reclaim: bool, max_retry: int) -> bool:
        self.calls.append(("acquire_execution", task_id, allow_reclaim, max_retry))
        return True

    def increment_consumer_retry_and_release(self, task_id: int, execution_id: str, reason: str | None) -> int:
        self.calls.append(("increment_consumer_retry_and_release", task_id, execution_id, reason))
        return 1

    def mark_failed_if_owner(self, task_id: int, execution_id: str, reason: str | None) -> int:
        self.calls.append(("mark_failed_if_owner", task_id, execution_id, reason))
        return 1

    def mark_failed_force(self, task_id: int, reason: str | None) -> int:
        self.calls.append(("mark_failed_force", task_id, reason))
        return 1


class FakeDispatchService:
    def __init__(self, side_effect=None):
        self.side_effect = side_effect
        self.calls: list[tuple[int, str]] = []

    async def run_task(self, task_id: int, execution_id: str) -> None:
        self.calls.append((task_id, execution_id))
        if self.side_effect:
            raise self.side_effect


class FakeProgressService:
    def __init__(self):
        self.calls: list[tuple] = []

    async def publish(self, event_type, task_id, execution_id, payload):
        self.calls.append((event_type, task_id, execution_id, payload))


async def _no_sleep(_: float) -> None:
    return None


class FakeQueue:
    def __init__(self):
        self.bind_calls: list[tuple[object, str]] = []
        self.consume_calls = 0

    async def bind(self, exchange, routing_key: str) -> None:
        self.bind_calls.append((exchange, routing_key))

    async def consume(self, callback) -> str:
        self.consume_calls += 1
        self.callback = callback
        return f"consumer-{self.consume_calls}"


class FakeChannel:
    def __init__(self):
        self.prefetch_count: int | None = None
        self.exchange_calls: list[tuple] = []
        self.queue = FakeQueue()
        self.closed = False

    async def set_qos(self, prefetch_count: int) -> None:
        self.prefetch_count = prefetch_count

    async def declare_exchange(self, name: str, exchange_type, durable: bool = True):
        exchange = SimpleNamespace(name=name, exchange_type=exchange_type, durable=durable)
        self.exchange_calls.append((name, exchange_type, durable))
        return exchange

    async def declare_queue(self, name: str, durable: bool = True):
        self.queue.name = name
        self.queue.durable = durable
        return self.queue

    async def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.channels: list[FakeChannel] = []
        self.closed = False

    async def channel(self) -> FakeChannel:
        channel = FakeChannel()
        self.channels.append(channel)
        return channel

    async def close(self) -> None:
        self.closed = True


def _build_settings(*, concurrency: int = 1, prefetch: int = 1):
    return SimpleNamespace(
        rabbitmq_host="127.0.0.1",
        rabbitmq_port=5672,
        rabbitmq_username="guest",
        rabbitmq_password="guest",
        rabbitmq_vhost="/",
        rabbitmq_prefetch=prefetch,
        rabbitmq_worker_concurrency=concurrency,
        task_dispatch_exchange="pricing.task.dispatch.exchange",
        task_dispatch_queue="pricing.task.dispatch.queue",
        task_dispatch_routing_key="pricing.task.dispatch",
        worker_max_retry=3,
        worker_retry_backoff_max_seconds=30,
    )


def test_on_message_acks_invalid_json():
    service = RabbitMqWorkerService(
        repo=FakeRepo(None),
        dispatch_service=FakeDispatchService(),
        progress_service=FakeProgressService(),
        sleep_func=_no_sleep,
    )
    message = FakeMessage(b"{bad-json")

    asyncio.run(service.on_message(message))

    assert message.acked == 1
    assert message.nacked == []


def test_on_message_acks_terminal_task_without_execution():
    service = RabbitMqWorkerService(
        repo=FakeRepo(FakeTask(task_status="FAILED")),
        dispatch_service=FakeDispatchService(),
        progress_service=FakeProgressService(),
        sleep_func=_no_sleep,
    )
    message = FakeMessage(json.dumps({"taskId": 12}).encode())

    asyncio.run(service.on_message(message))

    assert message.acked == 1
    assert message.nacked == []
    assert all(call[0] != "acquire_execution" for call in service.repo.calls)


def test_on_message_requeues_recoverable_error_after_releasing_execution():
    repo = FakeRepo(FakeTask(task_status="QUEUED"))
    dispatch = FakeDispatchService(side_effect=RecoverableError("temporary upstream failure"))
    progress = FakeProgressService()
    service = RabbitMqWorkerService(repo=repo, dispatch_service=dispatch, progress_service=progress, sleep_func=_no_sleep)
    message = FakeMessage(json.dumps({"taskId": 21}).encode())

    asyncio.run(service.on_message(message))

    assert message.acked == 0
    assert message.nacked == [True]
    assert any(call[0] == "increment_consumer_retry_and_release" for call in repo.calls)


def test_truncate_limits_error_text_to_255_characters():
    message = "x" * 300

    assert len(_truncate(message)) == 255
    assert _truncate(message).endswith("...")


def test_start_creates_configured_number_of_rabbitmq_consumers(monkeypatch):
    fake_connection = FakeConnection()
    fake_aio_pika = SimpleNamespace(
        ExchangeType=SimpleNamespace(DIRECT="direct"),
        connect_robust=lambda **_kwargs: _return_connection(fake_connection),
    )
    monkeypatch.setitem(sys.modules, "aio_pika", fake_aio_pika)

    service = RabbitMqWorkerService(settings=_build_settings(concurrency=3, prefetch=2), sleep_func=_no_sleep)

    async def _exercise():
        await service.start()
        await asyncio.sleep(0.05)
        snapshot = service.snapshot()
        await service.stop()
        return snapshot

    snapshot = asyncio.run(_exercise())

    assert len(fake_connection.channels) == 3
    assert [channel.prefetch_count for channel in fake_connection.channels] == [2, 2, 2]
    assert snapshot["workerConcurrency"] == 3
    assert snapshot["activeConsumers"] == 3


def test_stop_closes_all_consumer_channels_and_connection(monkeypatch):
    fake_connection = FakeConnection()
    fake_aio_pika = SimpleNamespace(
        ExchangeType=SimpleNamespace(DIRECT="direct"),
        connect_robust=lambda **_kwargs: _return_connection(fake_connection),
    )
    monkeypatch.setitem(sys.modules, "aio_pika", fake_aio_pika)

    service = RabbitMqWorkerService(settings=_build_settings(concurrency=2), sleep_func=_no_sleep)

    async def _exercise():
        await service.start()
        await asyncio.sleep(0.05)
        await service.stop()

    asyncio.run(_exercise())

    assert fake_connection.closed is True
    assert all(channel.closed for channel in fake_connection.channels)


async def _return_connection(connection: FakeConnection) -> FakeConnection:
    return connection
