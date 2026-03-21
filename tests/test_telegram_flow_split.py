from __future__ import annotations

import json

from app.models import GroupCache
from app.services import splitwise_service


def _ingest(client, message: str) -> str:
    payload = {
        "sender": "ICICIB",
        "contact_name": "ICICI Bank",
        "message": message,
        "received_at": "2026-03-21T13:31:00+05:30",
        "device_name": "Aditya iPhone",
    }
    ingest = client.post("/ingest/ios-sms", json=payload)
    return ingest.json()["transaction_id"]


def test_group_select_and_split_all_success(client, db_session, monkeypatch) -> None:
    tx_id = _ingest(client, "INR 1250 debited on card xx4321 at SWIGGY on 21-03-2026 13:30")

    db_session.add(
        GroupCache(
            group_id="g1",
            group_name="Goa Trip",
            members_json=json.dumps([{"id": "u1"}, {"id": "u2"}]),
        )
    )
    db_session.commit()

    choose = client.post(
        "/telegram/webhook",
        json={"callback_query": {"id": "cb1", "data": f"tx|{tx_id}|group|g1"}},
    )
    assert choose.status_code == 200

    monkeypatch.setattr(
        splitwise_service,
        "create_expense",
        lambda db, payload: splitwise_service.SplitwiseResult(
            ok=True,
            expense_id="sw1",
            detail="posted",
        ),
    )

    split = client.post(
        "/telegram/webhook",
        json={"callback_query": {"id": "cb2", "data": f"tx|{tx_id}|split_all|g1"}},
    )
    assert split.status_code == 200
    assert "posted" in split.json()["message"].lower()


def test_split_all_missing_amount_goes_draft(client, db_session) -> None:
    tx_id = _ingest(client, "Payment at unknown merchant")

    db_session.add(
        GroupCache(group_id="g2", group_name="Flatmates", members_json='[{"id":"u1"}]')
    )
    db_session.commit()

    split = client.post(
        "/telegram/webhook",
        json={"callback_query": {"id": "cb3", "data": f"tx|{tx_id}|split_all|g2"}},
    )
    assert split.status_code == 200
    assert "draft" in split.json()["message"].lower()
