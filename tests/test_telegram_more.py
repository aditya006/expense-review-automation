from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models import DraftAction, GroupCache
from app.services import telegram_service


def _ingest(client) -> str:
    payload = {
        "sender": "ICICIB",
        "contact_name": "ICICI Bank",
        "message": "INR 1250 debited on card xx4321 at SWIGGY on 21-03-2026 13:30",
        "received_at": "2026-03-21T13:31:00+05:30",
        "device_name": "Aditya iPhone",
    }
    ingest = client.post("/ingest/ios-sms", json=payload)
    assert ingest.status_code == 200
    return ingest.json()["transaction_id"]


def test_telegram_commands(client) -> None:
    for cmd in ["/start", "/help", "/pending", "/drafts", "/all_drafts", "/unknown"]:
        resp = client.post("/telegram/webhook", json={"message": {"text": cmd}})
        assert resp.status_code == 200


def test_telegram_invalid_callback_payload(client) -> None:
    resp = client.post("/telegram/webhook", json={"callback_query": {"data": "bad"}})
    assert resp.status_code == 400


def test_telegram_callback_tx_not_found(client) -> None:
    resp = client.post(
        "/telegram/webhook",
        json={"callback_query": {"data": "tx|does-not-exist|ignore"}},
    )
    assert resp.status_code == 404


def test_telegram_actions_ignore_draft_choose_group(client, db_session: Session) -> None:
    tx_id = _ingest(client)

    ignore_resp = client.post(
        "/telegram/webhook",
        json={"callback_query": {"data": f"tx|{tx_id}|ignore"}},
    )
    assert ignore_resp.status_code == 200

    tx_id_2 = _ingest(client)
    draft_resp = client.post(
        "/telegram/webhook",
        json={"callback_query": {"data": f"tx|{tx_id_2}|draft"}},
    )
    assert draft_resp.status_code == 200
    assert "draft" in draft_resp.json()["message"].lower()

    tx_id_3 = _ingest(client)
    no_group = client.post(
        "/telegram/webhook",
        json={"callback_query": {"data": f"tx|{tx_id_3}|choose_group"}},
    )
    assert no_group.status_code == 200

    db_session.add(
        GroupCache(
            group_id="g1",
            group_name="Goa Trip",
            members_json=json.dumps(
                [
                    {"id": "u1", "balance": [{"currency_code": "INR", "amount": "150.00"}]},
                    {"id": "u2", "balance": [{"currency_code": "INR", "amount": "-150.00"}]},
                ]
            ),
        )
    )
    db_session.commit()

    with_group = client.post(
        "/telegram/webhook",
        json={"callback_query": {"data": f"tx|{tx_id_3}|choose_group"}},
    )
    assert with_group.status_code == 200
    assert "group options" in with_group.json()["message"].lower()


def test_all_drafts_includes_non_open_status(client, db_session: Session) -> None:
    tx_id = _ingest(client)
    db_session.add(
        DraftAction(
            transaction_id=tx_id,
            draft_payload_json="{}",
            draft_status="manually_done",
        )
    )
    db_session.commit()

    resp = client.post("/telegram/webhook", json={"message": {"text": "/all_drafts"}})
    assert resp.status_code == 200
    assert "manually_done" in resp.json()["message"]


def test_choose_group_filters_out_settled_groups(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    tx_id = _ingest(client)

    db_session.add(
        GroupCache(
            group_id="g_settled",
            group_name="Settled Group",
            members_json=json.dumps(
                [
                    {"id": "u1", "balance": [{"currency_code": "INR", "amount": "0.00"}]},
                    {"id": "u2", "balance": [{"currency_code": "INR", "amount": "0.00"}]},
                ]
            ),
        )
    )
    db_session.add(
        GroupCache(
            group_id="g_unsettled",
            group_name="Unsettled Group",
            members_json=json.dumps(
                [
                    {"id": "u1", "balance": [{"currency_code": "INR", "amount": "50.00"}]},
                    {"id": "u2", "balance": [{"currency_code": "INR", "amount": "-50.00"}]},
                ]
            ),
        )
    )
    db_session.commit()

    captured: dict[str, object] = {}

    def _capture_message(*, text, chat_id=None, reply_markup=None):  # noqa: ANN001
        captured["text"] = text
        captured["reply_markup"] = reply_markup
        return "msg-1"

    monkeypatch.setattr(telegram_service, "send_text_message", _capture_message)

    resp = client.post(
        "/telegram/webhook",
        json={"callback_query": {"id": "cb-choose", "data": f"tx|{tx_id}|choose_group"}},
    )

    assert resp.status_code == 200
    keyboard = captured["reply_markup"]
    assert isinstance(keyboard, dict)
    callbacks = [
        button["callback_data"]
        for row in keyboard.get("inline_keyboard", [])
        for button in row
        if isinstance(button, dict) and "callback_data" in button
    ]
    assert any("g_unsettled" in cb for cb in callbacks)
    assert all("g_settled" not in cb for cb in callbacks)
