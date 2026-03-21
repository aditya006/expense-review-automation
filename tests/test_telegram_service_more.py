from __future__ import annotations

import pytest

from app.models import Transaction
from app.services import telegram_service


class _MockResponse:
    def __init__(self, payload: dict, *, fail: bool = False):
        self.payload = payload
        self.fail = fail

    def raise_for_status(self) -> None:
        if self.fail:
            raise RuntimeError("bad status")

    def json(self) -> dict:
        return self.payload


@pytest.fixture
def tx() -> Transaction:
    return Transaction(
        id="tx123",
        sender="HDFCBK",
        raw_message="Rs 200 spent",
        received_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        dedupe_key="k1",
        status="needs_review",
        source="ios_sms",
        currency="INR",
        amount_minor=20000,
        merchant="Cafe",
        channel="card",
    )


def test_send_text_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(telegram_service.settings, "telegram_bot_token", "bot")
    monkeypatch.setattr(telegram_service.settings, "telegram_chat_id", "123")
    monkeypatch.setattr(
        telegram_service.httpx,
        "post",
        lambda *a, **k: _MockResponse({"result": {"message_id": 77}}),
    )

    message_id = telegram_service.send_text_message(text="hello")
    assert message_id == "77"


def test_send_text_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(telegram_service.settings, "telegram_bot_token", "bot")
    monkeypatch.setattr(telegram_service.settings, "telegram_chat_id", "123")

    def _raise(*a, **k):
        raise RuntimeError("network")

    monkeypatch.setattr(telegram_service.httpx, "post", _raise)
    message_id = telegram_service.send_text_message(text="hello")
    assert message_id is None


def test_answer_callback_query(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(telegram_service.settings, "telegram_bot_token", "bot")
    monkeypatch.setattr(telegram_service.httpx, "post", lambda *a, **k: _MockResponse({"ok": True}))

    telegram_service.answer_callback_query("cb-id", text="ok")


def test_send_review_prompt_remote(monkeypatch: pytest.MonkeyPatch, tx: Transaction) -> None:
    monkeypatch.setattr(telegram_service.settings, "telegram_bot_token", "bot")
    monkeypatch.setattr(telegram_service.settings, "telegram_chat_id", "123")
    monkeypatch.setattr(
        telegram_service.httpx,
        "post",
        lambda *a, **k: _MockResponse({"result": {"message_id": 88}}),
    )

    message_id = telegram_service.send_review_prompt(tx)
    assert message_id == "88"
