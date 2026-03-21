from __future__ import annotations

from app.services import link_signing_service, splitwise_service


def test_root_and_health(client) -> None:
    root = client.get("/")
    assert root.status_code == 200
    assert root.json()["status"] == "ok"

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["ok"] is True


def test_splitwise_auth_endpoints(client, monkeypatch) -> None:
    start = client.get("/auth/splitwise/start")
    assert start.status_code == 200
    assert "oauth/authorize" in start.json()["authorize_url"]

    missing_code = client.get("/auth/splitwise/callback")
    assert missing_code.status_code == 200
    assert missing_code.json()["ok"] is False

    invalid_state = client.get("/auth/splitwise/callback?code=abc123&state=xyz")
    assert invalid_state.status_code == 400

    monkeypatch.setattr(splitwise_service, "exchange_code_for_token", lambda code: "token123")
    monkeypatch.setattr(splitwise_service, "save_access_token", lambda db, token: None)

    state = link_signing_service.create_oauth_state_token()
    callback = client.get(f"/auth/splitwise/callback?code=abc123&state={state}")
    assert callback.status_code == 200
    assert callback.json()["ok"] is True
