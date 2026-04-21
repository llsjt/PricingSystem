from app.core.config import Settings
from app.models.agent_run_log import AgentRunLog
from app.models.pricing_result import PricingResult
from app.models.pricing_task import PricingTask


def test_rabbitmq_async_columns_are_mapped():
    assert "consumer_retry_count" in PricingTask.__table__.c
    assert "current_execution_id" in PricingTask.__table__.c
    assert "execution_id" in AgentRunLog.__table__.c
    assert "execution_id" in PricingResult.__table__.c


def test_rabbitmq_settings_defaults_are_declared():
    settings = Settings()

    assert settings.rabbitmq_host == "127.0.0.1"
    assert settings.rabbitmq_port == 5672
    assert settings.rabbitmq_prefetch == 1
    assert settings.task_dispatch_exchange == "pricing.task.dispatch.exchange"
    assert settings.task_dispatch_queue == "pricing.task.dispatch.queue"
    assert settings.task_dispatch_routing_key == "pricing.task.dispatch"
    assert settings.task_progress_exchange == "pricing.task.progress.exchange"
    assert settings.task_progress_routing_key == "pricing.task.progress"
    assert settings.worker_max_retry == 3
    assert settings.worker_retry_backoff_max_seconds == 30
    assert settings.progress_publish_enabled is False
