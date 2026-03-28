from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="pricing-agent-backend", alias="APP_NAME")
    app_env: str = Field(default="dev", alias="APP_ENV")
    app_port: int = Field(default=8000, alias="APP_PORT")

    mysql_host: str = Field(default="localhost", alias="MYSQL_HOST")
    mysql_port: int = Field(default=3306, alias="MYSQL_PORT")
    mysql_db: str = Field(default="pricing_system2.0", alias="MYSQL_DB")
    mysql_user: str = Field(default="root", alias="MYSQL_USER")
    mysql_password: str = Field(default="", alias="MYSQL_PASSWORD")

    internal_api_token: str = Field(default="", alias="INTERNAL_API_TOKEN")
    python_base_prefix: str = Field(default="/internal", alias="PYTHON_BASE_PREFIX")

    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_base_url: str = Field(default="", alias="LLM_BASE_URL")
    llm_model: str = Field(default="qwen-plus", alias="MODEL")
    llm_timeout_seconds: int = Field(default=60, alias="LLM_TIMEOUT_SECONDS")
    llm_connect_timeout_seconds: int = Field(default=8, alias="LLM_CONNECT_TIMEOUT_SECONDS")
    llm_read_timeout_seconds: int = Field(default=25, alias="LLM_READ_TIMEOUT_SECONDS")
    llm_max_retries: int = Field(default=1, alias="LLM_MAX_RETRIES")
    llm_retry_backoff_seconds: float = Field(default=1.2, alias="LLM_RETRY_BACKOFF_SECONDS")

    crewai_agent_max_iter: int = Field(default=4, alias="CREWAI_AGENT_MAX_ITER")
    crewai_agent_max_execution_seconds: int = Field(default=40, alias="CREWAI_AGENT_MAX_EXEC_SECONDS")
    crewai_agent_max_retry_limit: int = Field(default=1, alias="CREWAI_AGENT_MAX_RETRY_LIMIT")
    crewai_session_timeout_seconds: int = Field(default=90, alias="CREWAI_SESSION_TIMEOUT_SECONDS")

    market_simulation_enabled: bool = Field(default=True, alias="MARKET_SIMULATION_ENABLED")

    @property
    def sqlalchemy_database_uri(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
