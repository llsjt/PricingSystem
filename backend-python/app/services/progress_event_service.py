"""进度事件服务，负责把任务和智能体阶段事件发布给 Java 后端。"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.core.config import get_settings
from app.services.runtime_metrics import get_runtime_metrics

logger = logging.getLogger(__name__)


class ProgressEventService:
    async def publish(self, event_type: str, task_id: int, execution_id: str | None, payload: dict) -> None:
        settings = get_settings()
        if not settings.progress_publish_enabled:
            return

        import aio_pika

        connection = None
        try:
            connection = await aio_pika.connect_robust(
                host=settings.rabbitmq_host,
                port=settings.rabbitmq_port,
                login=settings.rabbitmq_username,
                password=settings.rabbitmq_password,
                virtualhost=settings.rabbitmq_vhost,
            )
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
        except Exception:
            get_runtime_metrics().increment("progressPublishFailureCount")
            logger.warning("Progress event publish failed, taskId=%s eventType=%s", task_id, event_type, exc_info=True)
        finally:
            if connection is not None:
                await connection.close()

    def publish_sync(self, event_type: str, task_id: int, execution_id: str | None, payload: dict) -> None:
        try:
            asyncio.run(self.publish(event_type, task_id, execution_id, payload))
        except Exception:
            get_runtime_metrics().increment("progressPublishFailureCount")
            logger.warning("Progress event publish_sync failed, taskId=%s eventType=%s", task_id, event_type, exc_info=True)


_progress_event_service = ProgressEventService()


def get_progress_event_service() -> ProgressEventService:
    return _progress_event_service
