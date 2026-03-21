from __future__ import annotations

from sqlalchemy import select

from app import security
from app.models import GroupCache
from app.services import splitwise_service


def _ingest(client) -> str:
    payload = {
        "sender": "HDFCBK",
        "contact_name": "HDFC Bank",
        "message": "Rs 440 spent via card xx3333 at GROCERY Ref REF99",
        "received_at": "2026-03-21T12:00:00+05:30",
        "device_name": "Aditya iPhone",
    }
    resp = client.post("/ingest/ios-sms", json=payload)
    return resp.json()["transaction_id"]


def test_admin_routes_with_key(client, monkeypatch) -> None:
    monkeypatch.setattr(security.settings, "admin_api_key", "admin-secret")

    tx_id = _ingest(client)

    no_key = client.get(f"/admin/transactions/{tx_id}")
    assert no_key.status_code == 401

    with_key = client.get(
        f"/admin/transactions/{tx_id}",
        headers={"X-Admin-Key": "admin-secret"},
    )
    assert with_key.status_code == 200
    assert with_key.json()["id"] == tx_id

    reparse = client.post(
        f"/admin/reparse/{tx_id}",
        headers={"X-Admin-Key": "admin-secret"},
    )
    assert reparse.status_code == 200


def test_sync_groups_updates_cache(client, db_session, monkeypatch) -> None:
    monkeypatch.setattr(security.settings, "admin_api_key", "admin-secret")

    monkeypatch.setattr(
        splitwise_service,
        "fetch_groups",
        lambda db: [
            {
                "id": "g100",
                "name": "Goa Trip",
                "members": [{"id": "u1"}, {"id": "u2"}],
            }
        ],
    )

    resp = client.post(
        "/auth/splitwise/sync-groups",
        headers={"X-Admin-Key": "admin-secret"},
    )
    assert resp.status_code == 200
    assert resp.json()["count"] == 1

    group = db_session.scalar(select(GroupCache).where(GroupCache.group_id == "g100"))
    assert group is not None
