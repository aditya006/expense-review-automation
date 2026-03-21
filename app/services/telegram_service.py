from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings
from app.models import Transaction
from app.services import link_signing_service

logger = logging.getLogger(__name__)
settings = get_settings()


def _telegram_api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"


def _format_review_message(tx: Transaction) -> str:
    amount = "unknown"
    if tx.amount_minor is not None:
        amount = f"Rs {tx.amount_minor / 100:.2f}"

    merchant = tx.merchant or "unknown merchant"
    channel = tx.channel or "unknown"
    tail = f" ending {tx.last4}" if tx.last4 else ""
    review_link = link_signing_service.build_review_link(tx.id)
    return (
        f"Spent {amount} at {merchant} via {channel}{tail}. What should I do?\n"
        f"Open form: {review_link}"
    )


def _build_primary_keyboard(tx_id: str) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "Me Only", "callback_data": f"tx|{tx_id}|me_only"},
                {"text": "Choose Group", "callback_data": f"tx|{tx_id}|choose_group"},
            ],
            [
                {"text": "Draft", "callback_data": f"tx|{tx_id}|draft"},
                {"text": "Ignore", "callback_data": f"tx|{tx_id}|ignore"},
            ],
        ]
    }


def send_text_message(
    *,
    text: str,
    chat_id: str | int | None = None,
    reply_markup: dict[str, Any] | None = None,
) -> str | None:
    if not settings.telegram_bot_token:
        logger.info("Telegram bot token missing; text not sent")
        return None

    target_chat_id = str(chat_id) if chat_id is not None else settings.telegram_chat_id
    if not target_chat_id:
        logger.info("Telegram chat id missing; text not sent")
        return None

    payload: dict[str, Any] = {
        "chat_id": target_chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        response = httpx.post(_telegram_api_url("sendMessage"), json=payload, timeout=8.0)
        response.raise_for_status()
        data = response.json()
        message_id = data.get("result", {}).get("message_id")
        return str(message_id) if message_id is not None else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram sendMessage failed: %s", exc)
        return None


def answer_callback_query(callback_query_id: str, text: str | None = None) -> None:
    if not settings.telegram_bot_token:
        return

    payload: dict[str, Any] = {
        "callback_query_id": callback_query_id,
    }
    if text:
        payload["text"] = text

    try:
        response = httpx.post(_telegram_api_url("answerCallbackQuery"), json=payload, timeout=5.0)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram answerCallbackQuery failed: %s", exc)


def send_review_prompt(tx: Transaction) -> str:
    message = _format_review_message(tx)

    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.info("Telegram credentials missing; prompt not sent for tx=%s", tx.id)
        return f"local-{tx.id}"

    message_id = send_text_message(
        text=message,
        chat_id=settings.telegram_chat_id,
        reply_markup=_build_primary_keyboard(tx.id),
    )
    return message_id if message_id is not None else f"failed-{tx.id}"
