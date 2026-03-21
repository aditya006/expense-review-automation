from __future__ import annotations


def test_telegram_me_only_action_marks_ignored(client) -> None:
    ingest_payload = {
        "sender": "ICICIB",
        "contact_name": "ICICI Bank",
        "message": "INR 1250 debited on card xx4321 at SWIGGY on 21-03-2026 13:30",
        "received_at": "2026-03-21T13:31:00+05:30",
        "device_name": "Aditya iPhone",
    }
    ingest = client.post("/ingest/ios-sms", json=ingest_payload)
    tx_id = ingest.json()["transaction_id"]

    callback = {
        "update_id": 1,
        "callback_query": {
            "id": "cb1",
            "from": {"id": 123, "is_bot": False, "first_name": "Aditya"},
            "data": f"tx|{tx_id}|me_only",
        },
    }
    response = client.post("/telegram/webhook", json=callback)

    assert response.status_code == 200
    assert "me-only" in response.json()["message"].lower()
