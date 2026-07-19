from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite:///./change_radar.db"
    cache_backend: Literal["null", "memory", "redis"] = "memory"
    redis_url: str = "redis://localhost:6379/0"
    auto_create_tables: bool = False
    seed_demo_data: bool = True
    internal_user_key: str = "internal-demo"
    market_data_provider: Literal["database_demo", "sina", "eastmoney"] = "sina"
    market_sync_interval_seconds: int = 15
    market_candidate_limit_per_board: int = 20
    market_http_timeout_seconds: int = 12
    market_http_use_environment_proxy: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
