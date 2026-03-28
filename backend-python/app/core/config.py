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

    dashscope_api_key: str = Field(default="", alias="DASHSCOPE_API_KEY")
    agent_model: str = Field(default="qwen-plus", alias="AGENT_MODEL")

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

