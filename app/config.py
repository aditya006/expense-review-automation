from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_base_url: str = "http://localhost:8000"
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    telegram_chat_id: str = ""
    splitwise_client_id: str = ""
    splitwise_client_secret: str = ""
    splitwise_redirect_uri: str = ""
    splitwise_access_token: str = ""
    database_url: str = "sqlite:///./expense_bot.db"
    signing_secret: str = "change-me"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
