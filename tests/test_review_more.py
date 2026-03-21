from __future__ import annotations

from app.services import link_signing_service


def _ingest(client, message: str) -> str:
    payload = {
        "sender": "AXISBK",
        "contact_name": "Axis Bank",
        "message": message,
        "received_at": "2026-03-21T20:06:00+05:30",
        "device_name": "Aditya iPhone",
    }
    resp = client.post("/ingest/ios-sms", json=payload)
    assert resp.status_code == 200
    return resp.json()["transaction_id"]


def test_review_not_found(client) -> None:
    token = link_signing_service.create_review_token("missing-id")
    resp = client.post(
        f"/review/missing-id?t={token}",
        json={"action": "ignore", "participant_ids": [], "split_mode": "equal"},
    )
    assert resp.status_code == 404


def test_review_ignore_and_manual_done(client) -> None:
    tx_id = _ingest(client, "Rs 999 spent via UPI to CAFE Ref UPI123")
    token = link_signing_service.create_review_token(tx_id)

    ignore_resp = client.post(
        f"/review/{tx_id}?t={token}",
        json={"action": "ignore", "participant_ids": [], "split_mode": "equal"},
    )
    assert ignore_resp.status_code == 200
    assert ignore_resp.json()["status"] == "ignored"

    tx_id_2 = _ingest(client, "Rs 1200 spent via UPI to STORE Ref UPI456")
    token2 = link_signing_service.create_review_token(tx_id_2)
    manual_resp = client.post(
        f"/review/{tx_id_2}?t={token2}",
        json={"action": "manually_done", "participant_ids": [], "split_mode": "equal"},
    )
    assert manual_resp.status_code == 200
    assert "manually" in manual_resp.json()["detail"].lower()


def test_review_post_amount_missing_goes_to_draft(client) -> None:
    tx_id = _ingest(client, "Payment done at unknown merchant")
    token = link_signing_service.create_review_token(tx_id)

    post_resp = client.post(
        f"/review/{tx_id}?t={token}",
        json={
            "action": "post",
            "participant_ids": ["u1", "u2"],
            "split_mode": "equal",
        },
    )
    assert post_resp.status_code == 200
    assert post_resp.json()["status"] == "draft"


def test_review_get_form_renders(client) -> None:
    tx_id = _ingest(client, "Rs 200 spent via card xx1111 at CAFE")
    token = link_signing_service.create_review_token(tx_id)
    form_resp = client.get(f"/review/{tx_id}?t={token}")
    assert form_resp.status_code == 200
    assert "Review Expense" in form_resp.text
