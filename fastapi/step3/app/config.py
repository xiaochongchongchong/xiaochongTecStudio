from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从 .env 读取配置（原理：pydantic-settings 读环境变量/文件）"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "My App"
    SECRET_KEY: str = "change-me-in-env"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    DEBUG: bool = False


settings = Settings()
