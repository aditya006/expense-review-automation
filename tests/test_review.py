from __future__ import annotations

from app.services import link_signing_service


def _ingest(client):
    payload = {
        "sender": "AXISBK",
        "contact_name": "Axis Bank",
        "message": "Rs 2200 spent via UPI to ZEPTO Ref UPI12345 on 21-03-2026 20:05",
        "received_at": "2026-03-21T20:06:00+05:30",
        "device_name": "Aditya iPhone",
    }
    resp = client.post("/ingest/ios-sms", json=payload)
    assert resp.status_code == 200
    return resp.json()["transaction_id"]


def test_review_draft_action(client) -> None:
    tx_id = _ingest(client)
    token = link_signing_service.create_review_token(tx_id)

    review = {
        "group_id": "group_1",
        "participant_ids": ["u1", "u2"],
        "split_mode": "equal",
        "description": "Groceries",
        "notes": "Draft this",
        "action": "draft",
    }
    resp = client.post(f"/review/{tx_id}?t={token}", json=review)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "draft"


def test_review_post_without_token_falls_back_to_draft(client) -> None:
    tx_id = _ingest(client)
    token = link_signing_service.create_review_token(tx_id)

    review = {
        "group_id": "group_1",
        "participant_ids": ["u1", "u2", "u3"],
        "split_mode": "equal",
        "description": "Dinner",
        "notes": "Post attempt",
        "action": "post",
    }
    resp = client.post(f"/review/{tx_id}?t={token}", json=review)

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert data["status"] == "draft"
