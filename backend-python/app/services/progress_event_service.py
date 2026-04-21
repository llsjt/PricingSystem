import asyncio
import json
from datetime import datetime, timezone
from uuid import uuid4

from app.core.config import get_settings


class ProgressEventService:
    async def publish(self, event_type: str, task_id: int, execution_id: str | None, payload: dict) -> None:
        settings = get_settings()
        if not settings.progress_publish_enabled:
            return

        import aio_pika

        connection = await aio_pika.connect_robust(
            host=settings.rabbitmq_host,
            port=settings.rabbitmq_port,
            login=settings.rabbitmq_username,
            password=settings.rabbitmq_password,
            virtualhost=settings.rabbitmq_vhost,
        )
        try:
            channel = await connection.channel()
            exchange = await channel.declare_exchange(settings.task_progress_exchange, aio_pika.ExchangeType.DIRECT, durable=True)
            body = json.dumps(
                {
                    "eventId": str(uuid4()),
                    "eventType": event_type,
                    "taskId": int(task_id),
                    "executionId": execution_id,
                    "traceId": None,
                    "payload": payload,
                    "occurredAt": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                }
            ).encode("utf-8")
            await exchange.publish(
                aio_pika.Message(body=body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
                routing_key=settings.task_progress_routing_key,
            )
        finally:
            await connection.close()

    def publish_sync(self, event_type: str, task_id: int, execution_id: str | None, payload: dict) -> None:
        asyncio.run(self.publish(event_type, task_id, execution_id, payload))


_progress_event_service = ProgressEventService()


def get_progress_event_service() -> ProgressEventService:
    return _progress_event_service
