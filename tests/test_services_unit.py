from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Transaction
from app.services import dedupe_service, parser_service, splitwise_service, telegram_service


class _MockResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_dedupe_key_priority() -> None:
    ref_key = dedupe_service.compute_dedupe_key(
        sender="HDFCBK",
        normalized_message="abc",
        reference_id="REF123",
        amount_minor=100,
        last4="1234",
        merchant="Zepto",
        occurred_at=datetime.now(UTC),
    )
    assert ref_key.startswith("ref:")

    combo_key = dedupe_service.compute_dedupe_key(
        sender="HDFCBK",
        normalized_message="abc",
        reference_id=None,
        amount_minor=100,
        last4="1234",
        merchant="Zepto",
        occurred_at=datetime(2026, 3, 21, 10, 10, tzinfo=UTC),
    )
    assert combo_key.startswith("combo:")

    hash_key = dedupe_service.compute_dedupe_key(
        sender="HDFCBK",
        normalized_message="abc",
        reference_id=None,
        amount_minor=None,
        last4=None,
        merchant=None,
        occurred_at=None,
    )
    assert hash_key.startswith("hash:")


def test_parser_covers_sbi_family() -> None:
    result = parser_service.parse_sms(
        sender="SBICRD",
        message="Rs 450 spent on card xx9900 at CAFE REF TXN12",
        received_at=datetime.now(UTC),
    )
    assert result.is_transaction is True
    assert result.channel == "card"


def test_telegram_service_local_fallback() -> None:
    tx = Transaction(
        id="tx1",
        sender="HDFCBK",
        raw_message="sample",
        received_at=datetime.now(UTC),
        dedupe_key="k1",
        status="needs_review",
        source="ios_sms",
        currency="INR",
    )
    message_id = telegram_service.send_review_prompt(tx)
    assert message_id.startswith("local-") or message_id.startswith("failed-")


def test_splitwise_create_expense_success(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    monkeypatch.setattr(splitwise_service.settings, "splitwise_access_token", "token123")

    def mock_post(*args, **kwargs):  # noqa: ANN002, ANN003
        return _MockResponse({"expenses": [{"id": "sw123"}]})

    monkeypatch.setattr(splitwise_service.httpx, "post", mock_post)
    try:
        result = splitwise_service.create_expense(db, {"description": "Dinner", "cost": 500})
        assert result.ok is True
        assert result.expense_id == "sw123"
    finally:
        db.close()
        engine.dispose()


def test_splitwise_create_expense_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    monkeypatch.setattr(splitwise_service.settings, "splitwise_access_token", "token123")

    def mock_post(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("network down")

    monkeypatch.setattr(splitwise_service.httpx, "post", mock_post)
    try:
        result = splitwise_service.create_expense(db, {"description": "Dinner", "cost": 500})
        assert result.ok is False
    finally:
        db.close()
        engine.dispose()


def test_splitwise_auth_url() -> None:
    url = splitwise_service.authorization_url("state123")
    assert "oauth/authorize" in url
    assert "response_type=code" in url
