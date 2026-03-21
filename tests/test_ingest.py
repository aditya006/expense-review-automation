from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Transaction


def _payload() -> dict[str, str]:
    return {
        "sender": "HDFCBK",
        "contact_name": "HDFC Bank",
        "message": "Rs.850 spent on HDFC Bank Card xx1234 at ZEPTO on 20-03-2026 14:04 Ref ABC123",
        "received_at": "2026-03-20T14:05:21+05:30",
        "device_name": "Aditya iPhone",
    }


def test_ingest_creates_transaction(client, db_session: Session) -> None:
    response = client.post("/ingest/ios-sms", json=_payload())
    assert response.status_code == 200
    data = response.json()

    assert data["ok"] is True
    assert data["status"] == "needs_review"
    assert data["transaction_id"]

    tx = db_session.scalar(select(Transaction).where(Transaction.id == data["transaction_id"]))
    assert tx is not None
    assert tx.sender == "HDFCBK"


def test_ingest_deduplicates_same_message(client) -> None:
    first = client.post("/ingest/ios-sms", json=_payload())
    assert first.status_code == 200

    second = client.post("/ingest/ios-sms", json=_payload())
    assert second.status_code == 200
    second_data = second.json()

    assert second_data["duplicate"] is True
    assert second_data["transaction_id"] == first.json()["transaction_id"]
