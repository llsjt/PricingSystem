"""派发发布服务，负责把待执行任务投递到异步工作队列。"""

import json
from datetime import datetime, timezone
from uuid import uuid4

from app.core.config import get_settings


class DispatchPublisherService:
    async def publish_task(self, task_id: int, trace_id: str | None) -> None:
        import aio_pika

        settings = get_settings()
        connection = await aio_pika.connect_robust(
            host=settings.rabbitmq_host,
            port=settings.rabbitmq_port,
            login=settings.rabbitmq_username,
            password=settings.rabbitmq_password,
            virtualhost=settings.rabbitmq_vhost,
        )
        try:
            channel = await connection.channel()
            exchange = await channel.declare_exchange(settings.task_dispatch_exchange, aio_pika.ExchangeType.DIRECT, durable=True)
            queue = await channel.declare_queue(settings.task_dispatch_queue, durable=True)
            await queue.bind(exchange, routing_key=settings.task_dispatch_routing_key)
            body = json.dumps(
                {
                    "eventId": str(uuid4()),
                    "taskId": int(task_id),
                    "traceId": trace_id,
                    "occurredAt": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                }
            ).encode("utf-8")
            await exchange.publish(
                aio_pika.Message(body=body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
                routing_key=settings.task_dispatch_routing_key,
            )
        finally:
            await connection.close()


_dispatch_publisher_service = DispatchPublisherService()


def get_dispatch_publisher_service() -> DispatchPublisherService:
    return _dispatch_publisher_service
