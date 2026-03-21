from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_base_url: str = "http://localhost:8000"
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    telegram_chat_id: str = ""
    ingest_api_key: str = ""
    admin_api_key: str = ""
    splitwise_client_id: str = ""
    splitwise_client_secret: str = ""
    splitwise_redirect_uri: str = ""
    splitwise_access_token: str = ""
    database_url: str = "sqlite:///./expense_bot.db"
    signing_secret: str = ""
    log_level: str = "INFO"
    review_link_ttl_seconds: int = 86400
    splitwise_oauth_state_ttl_seconds: int = 900
    disable_docs_in_production: bool = True
    allowed_hosts: str = "*"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
