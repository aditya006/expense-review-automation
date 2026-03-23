from __future__ import annotations

import httpx
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

    result = splitwise_service.create_expense(
        db_session,
        {"description": "x", "cost": 1, "group_id": "1", "split_mode": "equal"},
    )
    assert result.ok is False


def test_create_expense_builds_equal_group_payload(
    monkeypatch: pytest.MonkeyPatch,
    db_session,
) -> None:
    monkeypatch.setattr(splitwise_service, "_headers", lambda db: {"Authorization": "Bearer t"})
    captured: dict[str, object] = {}

    def _mock_post(*args, **kwargs):  # noqa: ANN002, ANN003
        captured["json"] = kwargs.get("json")
        return _MockResponse({"expenses": [{"id": "sw-equal"}]})

    monkeypatch.setattr(splitwise_service.httpx, "post", _mock_post)

    result = splitwise_service.create_expense(
        db_session,
        {
            "description": "Groceries",
            "cost_minor": 321,
            "cost": 3.21,
            "currency_code": "INR",
            "group_id": "123",
            "split_mode": "equal",
            "participant_ids": [],
        },
    )

    assert result.ok is True
    assert result.expense_id == "sw-equal"
    payload = captured["json"]
    assert isinstance(payload, dict)
    assert payload["group_id"] == 123
    assert payload["cost"] == "3.21"
    assert payload["split_equally"] is True
    assert "split_mode" not in payload


def test_create_expense_builds_share_payload_for_selected_people(
    monkeypatch: pytest.MonkeyPatch,
    db_session,
) -> None:
    monkeypatch.setattr(splitwise_service, "_headers", lambda db: {"Authorization": "Bearer t"})
    monkeypatch.setattr(splitwise_service, "_current_user_id", lambda db: 99)
    captured: dict[str, object] = {}

    def _mock_post(*args, **kwargs):  # noqa: ANN002, ANN003
        captured["json"] = kwargs.get("json")
        return _MockResponse({"expenses": [{"id": "sw-share"}]})

    monkeypatch.setattr(splitwise_service.httpx, "post", _mock_post)

    result = splitwise_service.create_expense(
        db_session,
        {
            "description": "Utilities",
            "cost_minor": 1000,
            "group_id": "777",
            "split_mode": "equal",
            "participant_ids": ["11", "12"],
        },
    )

    assert result.ok is True
    payload = captured["json"]
    assert isinstance(payload, dict)
    assert payload["group_id"] == 777
    # payer is auto-added and fully paid.
    assert payload["users__2__user_id"] == 99
    assert payload["users__2__paid_share"] == "10.00"
    # owed shares should sum to total.
    owed = [
        float(payload["users__0__owed_share"]),
        float(payload["users__1__owed_share"]),
        float(payload["users__2__owed_share"]),
    ]
    assert round(sum(owed), 2) == 10.00


def test_create_expense_http_error_includes_response_body(
    monkeypatch: pytest.MonkeyPatch,
    db_session,
) -> None:
    monkeypatch.setattr(splitwise_service, "_headers", lambda db: {"Authorization": "Bearer t"})

    def _mock_post(*args, **kwargs):  # noqa: ANN002, ANN003
        request = httpx.Request("POST", "https://secure.splitwise.com/api/v3.0/create_expense")
        response = httpx.Response(
            400,
            request=request,
            text='{"errors":{"base":["Unrecognized parameter `split_mode`"]}}',
        )
        raise httpx.HTTPStatusError("bad request", request=request, response=response)

    monkeypatch.setattr(splitwise_service.httpx, "post", _mock_post)

    result = splitwise_service.create_expense(
        db_session,
        {"description": "x", "cost": 1, "group_id": "1", "split_mode": "equal"},
    )
    assert result.ok is False
    assert "splitwise_error:400" in result.detail
    assert "Unrecognized parameter" in result.detail
