from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import GroupCache


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
    for cmd in ["/start", "/help", "/pending", "/drafts", "/unknown"]:
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
        GroupCache(group_id="g1", group_name="Goa Trip", members_json='["u1","u2"]')
    )
    db_session.commit()

    with_group = client.post(
        "/telegram/webhook",
        json={"callback_query": {"data": f"tx|{tx_id_3}|choose_group"}},
    )
    assert with_group.status_code == 200
    assert "goa trip" in with_group.json()["message"].lower()
