import json
from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    app_debug: bool = True
    app_name: str = "Lead Bot"

    bot_token: str = "123456:ABC"
    bot_mode: str = "polling"
    bot_webhook_url: str = "https://example.com/webhook/telegram"
    bot_webhook_secret: str = "change-me"

    admin_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)
    admin_api_token: str = "change-me-admin-token"
    manager_group_id: int | None = None

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/leadbot"
    redis_url: str = "redis://localhost:6379/0"

    timezone: str = "Europe/Moscow"

    rate_limit_messages_per_minute: int = 20
    max_leads_per_10_minutes: int = 3
    max_files_per_lead: int = 5
    max_file_size_mb: int = 20
    fsm_ttl_hours: int = 24
    drop_pending_updates: bool = False

    sentry_dsn: str | None = None

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: str | int | list[int] | tuple[int, ...] | None) -> list[int]:
        if value is None or value == "":
            return []
        if isinstance(value, int):
            return [value]
        if isinstance(value, list | tuple):
            return [int(item) for item in value]
        value = value.strip()
        if not value:
            return []
        if value.startswith("["):
            decoded = json.loads(value)
            if isinstance(decoded, int):
                return [decoded]
            return [int(item) for item in decoded]
        return [int(item.strip()) for item in value.split(",") if item.strip()]

    @field_validator("manager_group_id", mode="before")
    @classmethod
    def parse_optional_int(cls, value: str | int | None) -> int | None:
        if value in (None, ""):
            return None
        return int(value)

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
