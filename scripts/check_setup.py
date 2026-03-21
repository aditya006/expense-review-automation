#!/usr/bin/env python3
from __future__ import annotations

from app.config import get_settings
from app.security import validate_runtime_config


def _ok(label: str, value: bool) -> None:
    mark = "OK" if value else "MISSING"
    print(f"[{mark}] {label}")


def main() -> None:
    settings = get_settings()

    print(f"APP_ENV={settings.app_env}")
    _ok("APP_BASE_URL", bool(settings.app_base_url))
    _ok("INGEST_API_KEY", bool(settings.ingest_api_key))
    _ok("TELEGRAM_BOT_TOKEN", bool(settings.telegram_bot_token))
    _ok("TELEGRAM_WEBHOOK_SECRET", bool(settings.telegram_webhook_secret))
    _ok("TELEGRAM_CHAT_ID", bool(settings.telegram_chat_id))
    _ok(
        "SIGNING_SECRET(>=16 chars)",
        bool(settings.signing_secret) and len(settings.signing_secret) >= 16,
    )
    _ok("SPLITWISE_CLIENT_ID", bool(settings.splitwise_client_id))
    _ok("SPLITWISE_CLIENT_SECRET", bool(settings.splitwise_client_secret))
    _ok("SPLITWISE_REDIRECT_URI", bool(settings.splitwise_redirect_uri))

    if settings.app_env.lower() == "production":
        try:
            validate_runtime_config()
            print("Production security validation: OK")
        except RuntimeError as exc:
            print(f"Production security validation: FAIL ({exc})")


if __name__ == "__main__":
    main()
