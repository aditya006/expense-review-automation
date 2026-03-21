from __future__ import annotations


def test_root_and_health(client) -> None:
    root = client.get("/")
    assert root.status_code == 200
    assert root.json()["status"] == "ok"

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["ok"] is True


def test_splitwise_auth_endpoints(client) -> None:
    start = client.get("/auth/splitwise/start")
    assert start.status_code == 200
    assert "oauth/authorize" in start.json()["authorize_url"]

    missing_code = client.get("/auth/splitwise/callback")
    assert missing_code.status_code == 200
    assert missing_code.json()["ok"] is False

    callback = client.get("/auth/splitwise/callback?code=abc123&state=xyz")
    assert callback.status_code == 200
    assert callback.json()["ok"] is True
