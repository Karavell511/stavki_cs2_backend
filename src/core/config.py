from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    app_name: str = "stavki-cs2-backend"
    environment: str = "dev"
    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")
    bot_token: str = Field(alias="BOT_TOKEN")
    jwt_secret: str = Field(alias="JWT_SECRET")
    jwt_expire_minutes: int = Field(default=120, alias="JWT_EXPIRE_MINUTES")
    telegram_admin_ids: str = Field(default="", alias="TELEGRAM_ADMIN_IDS")
    cors_origins: str = "*"

    @property
    def parsed_admin_ids(self) -> List[int]:
        if not self.telegram_admin_ids.strip():
            return []
        return [int(v.strip()) for v in self.telegram_admin_ids.split(",") if v.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[arg-type]
