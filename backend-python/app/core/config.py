from pydantic_settings import BaseSettings
from typing import Optional
import os
from pathlib import Path

# 获取 .env 文件的绝对路径
env_path = Path(__file__).parent.parent.parent / ".env"

class Settings(BaseSettings):
    """
    项目核心配置类
    支持从环境变量自动加载配置
    """
    # 基础配置
    APP_NAME: str = "Multi-Agent E-commerce Decision System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # LLM 配置
    OPENAI_API_KEY: str = ""  # 从 .env 文件读取，禁止硬编码
    OPENAI_MODEL_NAME: str = "qwen3.5-plus"
    OPENAI_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    # MySQL 配置
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""  # 从 .env 文件读取，禁止硬编码
    MYSQL_DB: str = "pricing_system"

    # Redis 配置 (预留)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # Chroma 配置 (预留)
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    CHROMA_DB_PATH: str = "./chroma_db"

    class Config:
        env_file = str(env_path)
        env_file_encoding = "utf-8"
        # 允许额外的环境变量存在而不报错
        extra = "ignore"

# 实例化配置对象，供全局使用
settings = Settings()
