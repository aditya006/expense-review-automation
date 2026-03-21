from __future__ import annotations

import pytest

from app import security
from app.services import link_signing_service


def _ingest_payload() -> dict[str, str]:
    return {
        "sender": "HDFCBK",
        "contact_name": "HDFC Bank",
        "message": "Rs.100 spent on card xx1111 at TEST Ref AB12",
        "received_at": "2026-03-21T10:00:00+05:30",
        "device_name": "Aditya iPhone",
    }


def test_ingest_requires_api_key_when_configured(client, monkeypatch) -> None:
    monkeypatch.setattr(security.settings, "ingest_api_key", "ingest-secret")

    unauthorized = client.post("/ingest/ios-sms", json=_ingest_payload())
    assert unauthorized.status_code == 401

    authorized = client.post(
        "/ingest/ios-sms",
        json=_ingest_payload(),
        headers={"X-Ingest-Key": "ingest-secret"},
    )
    assert authorized.status_code == 200


def test_telegram_webhook_requires_secret_when_configured(client, monkeypatch) -> None:
    monkeypatch.setattr(security.settings, "telegram_webhook_secret", "tg-secret")

    unauthorized = client.post("/telegram/webhook", json={"message": {"text": "/start"}})
    assert unauthorized.status_code == 401

    authorized = client.post(
        "/telegram/webhook",
        json={"message": {"text": "/start"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "tg-secret"},
    )
    assert authorized.status_code == 200


def test_review_requires_signed_token(client) -> None:
    ingest = client.post("/ingest/ios-sms", json=_ingest_payload())
    tx_id = ingest.json()["transaction_id"]

    without_token = client.get(f"/review/{tx_id}")
    assert without_token.status_code == 401

    token = link_signing_service.create_review_token(tx_id)
    with_token = client.get(f"/review/{tx_id}?t={token}")
    assert with_token.status_code == 200


def test_admin_endpoints_require_admin_key(client, monkeypatch) -> None:
    monkeypatch.setattr(security.settings, "admin_api_key", "admin-secret")

    forbidden = client.get("/admin/drafts")
    assert forbidden.status_code == 401

    ok = client.get("/admin/drafts", headers={"X-Admin-Key": "admin-secret"})
    assert ok.status_code == 200


def test_telegram_chat_restriction(client, monkeypatch) -> None:
    monkeypatch.setattr(security.settings, "telegram_chat_id", "999")
    monkeypatch.setattr(security.settings, "telegram_webhook_secret", "")

    blocked = client.post(
        "/telegram/webhook",
        json={"message": {"text": "/start", "chat": {"id": 123}}},
    )
    assert blocked.status_code == 403


def test_validate_runtime_config(monkeypatch) -> None:
    monkeypatch.setattr(security.settings, "app_env", "production")
    monkeypatch.setattr(security.settings, "ingest_api_key", "ingest")
    monkeypatch.setattr(security.settings, "telegram_webhook_secret", "telegram")
    monkeypatch.setattr(security.settings, "signing_secret", "x" * 24)
    security.validate_runtime_config()


def test_validate_runtime_config_missing_values(monkeypatch) -> None:
    monkeypatch.setattr(security.settings, "app_env", "production")
    monkeypatch.setattr(security.settings, "ingest_api_key", "")
    monkeypatch.setattr(security.settings, "telegram_webhook_secret", "")
    monkeypatch.setattr(security.settings, "signing_secret", "")
    with pytest.raises(RuntimeError):
        security.validate_runtime_config()
