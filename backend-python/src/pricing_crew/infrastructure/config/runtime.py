"""运行时配置模块，集中管理服务、数据库和抓取参数。"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[4]
RUNTIME_DIR = PROJECT_ROOT / "runtime"
_ENV_PATH = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_PATH), env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Crew Pricing Decision Service"
    app_version: str = "2.1.0"
    debug: bool = True

    openai_api_key: str = ""
    openai_model_name: str = "gpt-4o-mini"
    openai_api_base: str = ""
    crewai_enabled: bool = False

    database_url: str = ""
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_db: str = "pricing_system"
    bootstrap_demo_data: bool = False

    websocket_chunk_size: int = 24
    websocket_chunk_delay: float = 0.02
    websocket_min_stream_seconds: float = 2.0

    market_live_required_for_discount: bool = True

    def resolved_database_url(self) -> str:
        if self.database_url.strip():
            return self.database_url.strip()
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}@"
            f"{self.mysql_host}:{self.mysql_port}/{self.mysql_db}"
        )


settings = Settings()
