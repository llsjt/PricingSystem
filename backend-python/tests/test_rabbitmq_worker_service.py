import asyncio
import json

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
