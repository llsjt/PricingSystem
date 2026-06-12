import asyncio
import sys
from types import SimpleNamespace

from app.services.progress_event_service import ProgressEventService
from app.services.runtime_metrics import get_runtime_metrics


def test_progress_publish_failure_is_best_effort(monkeypatch):
    async def failing_connect(**_kwargs):  # noqa: ANN001
        raise RuntimeError("rabbitmq down")

    monkeypatch.setattr(
        "app.services.progress_event_service.get_settings",
        lambda: SimpleNamespace(
            progress_publish_enabled=True,
            rabbitmq_host="127.0.0.1",
            rabbitmq_port=5672,
            rabbitmq_username="guest",
            rabbitmq_password="guest",
            rabbitmq_vhost="/",
            task_progress_exchange="pricing.task.progress.exchange",
            task_progress_routing_key="pricing.task.progress",
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "aio_pika",
        SimpleNamespace(connect_robust=failing_connect),
    )
    before = get_runtime_metrics().snapshot()["progressPublishFailureCount"]

    asyncio.run(ProgressEventService().publish("TASK_STARTED", 1, "exec-1", {}))

    after = get_runtime_metrics().snapshot()["progressPublishFailureCount"]
    assert after == before + 1
