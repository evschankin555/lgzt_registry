from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class MaxBotSettings(BaseSettings):
    max_bot_token: str = ""
    max_webhook_secret: str = ""
    max_webhook_url: str = ""
    max_api_base_url: str = ""
    max_debug_log_payloads: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


@lru_cache()
def get_max_settings() -> MaxBotSettings:
    return MaxBotSettings()
