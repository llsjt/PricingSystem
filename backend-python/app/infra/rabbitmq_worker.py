"""RabbitMQ worker facade with graceful shutdown support."""

from app.services.rabbitmq_worker_service import RabbitMqWorkerService, RecoverableError, get_rabbitmq_worker_service

__all__ = ["RabbitMqWorkerService", "RecoverableError", "get_rabbitmq_worker_service"]
