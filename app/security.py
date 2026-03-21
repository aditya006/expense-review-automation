from __future__ import annotations

from fastapi import Header, HTTPException, Request, status

from app.config import get_settings

settings = get_settings()


def _is_production() -> bool:
    return settings.app_env.lower() == "production"


def validate_runtime_config() -> None:
    if not _is_production():
        return

    missing: list[str] = []
    if not settings.ingest_api_key:
        missing.append("INGEST_API_KEY")
    if not settings.telegram_webhook_secret:
        missing.append("TELEGRAM_WEBHOOK_SECRET")
    if not settings.signing_secret or len(settings.signing_secret) < 16:
        missing.append("SIGNING_SECRET (min 16 chars, non-default)")

    if missing:
        required = ", ".join(missing)
        raise RuntimeError(f"Missing required production security settings: {required}")


def verify_ingest_api_key(
    x_ingest_key: str | None = Header(default=None, alias="X-Ingest-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> None:
    expected_key = settings.ingest_api_key
    if not expected_key:
        if _is_production():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Server ingest auth not configured",
            )
        return

    provided = x_ingest_key
    if not provided and authorization and authorization.lower().startswith("bearer "):
        provided = authorization.split(" ", 1)[1].strip()

    if provided != expected_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized ingest")


def verify_admin_api_key(
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
) -> None:
    expected_key = settings.admin_api_key
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin API is disabled",
        )

    if x_admin_key != expected_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized admin")


def verify_telegram_webhook_secret(
    x_telegram_secret: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
) -> None:
    expected_secret = settings.telegram_webhook_secret
    if not expected_secret:
        if _is_production():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Server telegram webhook secret not configured",
            )
        return

    if x_telegram_secret != expected_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized webhook")


def enforce_single_user_chat(request: Request, payload: dict) -> None:
    expected_chat_id = settings.telegram_chat_id
    if not expected_chat_id:
        return

    chat_id: str | None = None
    if payload.get("message") and isinstance(payload.get("message"), dict):
        chat = payload["message"].get("chat")
        if isinstance(chat, dict) and chat.get("id") is not None:
            chat_id = str(chat["id"])

    if payload.get("callback_query") and isinstance(payload.get("callback_query"), dict):
        cb = payload["callback_query"]
        if cb.get("message") and isinstance(cb.get("message"), dict):
            chat = cb["message"].get("chat")
            if isinstance(chat, dict) and chat.get("id") is not None:
                chat_id = str(chat["id"])

    if chat_id and chat_id != str(expected_chat_id):
        client_host = request.client.host if request.client else "unknown"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Unexpected chat source from {client_host}",
        )
