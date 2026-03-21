from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.services import splitwise_service


class _MockResponse:
    def __init__(self, payload: dict, *, fail: bool = False):
        self.payload = payload
        self.fail = fail

    def raise_for_status(self) -> None:
        if self.fail:
            raise RuntimeError("http error")

    def json(self) -> dict:
        return self.payload


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_exchange_code_for_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(splitwise_service.settings, "splitwise_client_id", "cid")
    monkeypatch.setattr(splitwise_service.settings, "splitwise_client_secret", "csecret")

    monkeypatch.setattr(
        splitwise_service.httpx,
        "post",
        lambda *a, **k: _MockResponse({"access_token": "token123"}),
    )

    token = splitwise_service.exchange_code_for_token("code123")
    assert token == "token123"


def test_exchange_code_for_token_missing_creds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(splitwise_service.settings, "splitwise_client_id", "")
    monkeypatch.setattr(splitwise_service.settings, "splitwise_client_secret", "")
    with pytest.raises(RuntimeError):
        splitwise_service.exchange_code_for_token("code123")


def test_fetch_current_user_and_groups(monkeypatch: pytest.MonkeyPatch, db_session) -> None:
    monkeypatch.setattr(splitwise_service, "_headers", lambda db: {"Authorization": "Bearer t"})

    monkeypatch.setattr(
        splitwise_service.httpx,
        "get",
        lambda *a, **k: _MockResponse({"current_user": {"id": 1}, "groups": [{"id": "g1"}]}),
    )

    user = splitwise_service.fetch_current_user(db_session)
    groups = splitwise_service.fetch_groups(db_session)
    assert "current_user" in user
    assert isinstance(groups, list)


def test_create_expense_missing_id(monkeypatch: pytest.MonkeyPatch, db_session) -> None:
    monkeypatch.setattr(splitwise_service, "_headers", lambda db: {"Authorization": "Bearer t"})
    monkeypatch.setattr(
        splitwise_service.httpx,
        "post",
        lambda *a, **k: _MockResponse({"expenses": [{}]}),
    )

    result = splitwise_service.create_expense(db_session, {"description": "x", "cost": 1})
    assert result.ok is False
