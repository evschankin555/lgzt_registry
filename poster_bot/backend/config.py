from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Dashboard auth
    admin_password: str = "admin2026$rassilka"

    # JWT
    secret_key: str = "change-this-secret-key-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours

    # Telegram API
    telegram_api_id: int = 0
    telegram_api_hash: str = ""

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/poster.db"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
