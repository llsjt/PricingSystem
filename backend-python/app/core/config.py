"""应用配置模块，负责从环境变量读取 Python 协作端的运行参数。"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(BASE_DIR / ".env"), str(BASE_DIR / ".env.local")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="pricing-agent-backend", alias="APP_NAME")
    app_env: str = Field(default="dev", alias="APP_ENV")
    app_port: int = Field(default=8000, alias="APP_PORT")

    mysql_host: str = Field(default="localhost", alias="MYSQL_HOST")
    mysql_port: int = Field(default=3306, alias="MYSQL_PORT")
    mysql_db: str = Field(default="pricing_system2.0", alias="MYSQL_DB")
    mysql_user: str = Field(default="root", alias="MYSQL_USER")
    mysql_password: str = Field(default="", alias="MYSQL_PASSWORD")

    internal_api_token: str = Field(default="", alias="INTERNAL_API_TOKEN")
    allow_dev_internal_token_bypass: bool = Field(default=True, alias="ALLOW_DEV_INTERNAL_TOKEN_BYPASS")
    python_base_prefix: str = Field(default="/internal", alias="PYTHON_BASE_PREFIX")
    llm_key_encryption_secret: str = Field(default="", alias="LLM_KEY_ENCRYPTION_SECRET")

    agent_worker_concurrency: int = Field(default=2, alias="AGENT_WORKER_CONCURRENCY")
    agent_queue_maxsize: int = Field(default=100, alias="AGENT_QUEUE_MAXSIZE")
    agent_poll_interval_ms: int = Field(default=500, alias="AGENT_POLL_INTERVAL_MS")
    agent_max_retries: int = Field(default=2, alias="AGENT_MAX_RETRIES")
    rabbitmq_host: str = Field(default="127.0.0.1", alias="RABBITMQ_HOST")
    rabbitmq_port: int = Field(default=5672, alias="RABBITMQ_PORT")
    rabbitmq_username: str = Field(default="guest", alias="RABBITMQ_USERNAME")
    rabbitmq_password: str = Field(default="guest", alias="RABBITMQ_PASSWORD")
    rabbitmq_vhost: str = Field(default="/", alias="RABBITMQ_VHOST")
    rabbitmq_prefetch: int = Field(default=1, alias="RABBITMQ_PREFETCH")
    task_dispatch_exchange: str = Field(default="pricing.task.dispatch.exchange", alias="TASK_DISPATCH_EXCHANGE")
    task_dispatch_queue: str = Field(default="pricing.task.dispatch.queue", alias="TASK_DISPATCH_QUEUE")
    task_dispatch_routing_key: str = Field(default="pricing.task.dispatch", alias="TASK_DISPATCH_ROUTING_KEY")
    task_progress_exchange: str = Field(default="pricing.task.progress.exchange", alias="TASK_PROGRESS_EXCHANGE")
    task_progress_routing_key: str = Field(default="pricing.task.progress", alias="TASK_PROGRESS_ROUTING_KEY")
    worker_max_retry: int = Field(default=3, alias="WORKER_MAX_RETRY")
    worker_retry_backoff_max_seconds: int = Field(default=30, alias="WORKER_RETRY_BACKOFF_MAX_SECONDS")
    progress_publish_enabled: bool = Field(default=False, alias="PROGRESS_PUBLISH_ENABLED")

    competitor_data_source: Literal["tmall_csv"] = Field(default="tmall_csv", alias="COMPETITOR_DATA_SOURCE")
    market_competitor_min_valid_count: int = Field(default=3, alias="MARKET_COMPETITOR_MIN_VALID_COUNT")
    competitor_csv_index_path: str = Field(
        default=str(BASE_DIR / "app" / "data" / "competitor_index.sqlite"),
        alias="COMPETITOR_CSV_INDEX_PATH",
    )
    competitor_csv_sample_size: int = Field(default=8, alias="COMPETITOR_CSV_SAMPLE_SIZE")

    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_base_url: str = Field(default="", alias="LLM_BASE_URL")
    llm_model: str = Field(default="qwen-plus", alias="MODEL")
    llm_retry_backoff_seconds: float = Field(default=1.2, alias="LLM_RETRY_BACKOFF_SECONDS")

    crewai_llm_timeout_seconds: int = Field(default=240, alias="CREWAI_LLM_TIMEOUT_SECONDS")
    crewai_llm_connect_timeout_seconds: int = Field(default=10, alias="CREWAI_LLM_CONNECT_TIMEOUT_SECONDS")
    crewai_llm_read_timeout_seconds: int = Field(default=180, alias="CREWAI_LLM_READ_TIMEOUT_SECONDS")
    crewai_llm_max_retries: int = Field(default=1, alias="CREWAI_LLM_MAX_RETRIES")

    analysis_agent_max_iter: int = Field(
        default=4,
        validation_alias=AliasChoices("ANALYSIS_AGENT_MAX_ITER", "FAST_AGENT_MAX_ITER"),
    )
    analysis_agent_max_execution_seconds: int = Field(
        default=300,
        validation_alias=AliasChoices("ANALYSIS_AGENT_MAX_EXEC_SECONDS", "FAST_AGENT_MAX_EXEC_SECONDS"),
    )
    manager_agent_max_iter: int = Field(default=6, alias="MANAGER_AGENT_MAX_ITER")
    manager_agent_max_execution_seconds: int = Field(default=180, alias="MANAGER_AGENT_MAX_EXEC_SECONDS")
    crewai_agent_max_retry_limit: int = Field(default=1, alias="CREWAI_AGENT_MAX_RETRY_LIMIT")
    crewai_session_timeout_seconds: int = Field(default=600, alias="CREWAI_SESSION_TIMEOUT_SECONDS")
    crewai_debug_logs: bool = Field(default=False, alias="CREWAI_DEBUG_LOGS")

    @property
    def sqlalchemy_database_uri(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"
        )

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "prod"

    def validate_competitor_source(self) -> list[str]:
        return []

    def validate_production_safety(self) -> None:
        if not self.is_production:
            return

        problems: list[str] = []
        if not self.internal_api_token.strip():
            problems.append("blank internal api token")
        if not self.mysql_password.strip() or self.mysql_password.strip() == "123456":
            problems.append("unsafe mysql password")
        if problems:
            raise RuntimeError("Unsafe production configuration: " + ", ".join(problems))


@lru_cache
def get_settings() -> Settings:
    return Settings()
