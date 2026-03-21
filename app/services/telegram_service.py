from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings
from app.models import Transaction

logger = logging.getLogger(__name__)
settings = get_settings()


def _format_review_message(tx: Transaction) -> str:
    amount = "unknown"
    if tx.amount_minor is not None:
        amount = f"Rs {tx.amount_minor / 100:.2f}"

    merchant = tx.merchant or "unknown merchant"
    channel = tx.channel or "unknown"
    tail = f" ending {tx.last4}" if tx.last4 else ""
    return f"Spent {amount} at {merchant} via {channel}{tail}. What should I do?"


def _build_keyboard(tx_id: str) -> dict[str, Any]:
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


def send_review_prompt(tx: Transaction) -> str:
    message = _format_review_message(tx)

    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.info("Telegram credentials missing; prompt not sent for tx=%s", tx.id)
        return f"local-{tx.id}"

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": message,
        "reply_markup": _build_keyboard(tx.id),
    }

    try:
        response = httpx.post(url, json=payload, timeout=5.0)
        response.raise_for_status()
        data = response.json()
        message_id = data.get("result", {}).get("message_id")
        return str(message_id) if message_id is not None else f"remote-{tx.id}"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram send failed for tx=%s: %s", tx.id, exc)
        return f"failed-{tx.id}"
