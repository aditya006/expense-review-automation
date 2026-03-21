from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from app.config import get_settings

settings = get_settings()


@dataclass
class SplitwiseResult:
    ok: bool
    expense_id: str | None
    detail: str


def authorization_url() -> str:
    state = secrets.token_urlsafe(16)
    return (
        "https://secure.splitwise.com/oauth/authorize"
        f"?response_type=code&client_id={settings.splitwise_client_id}"
        f"&redirect_uri={settings.splitwise_redirect_uri}&state={state}"
    )


def create_expense(payload: dict) -> SplitwiseResult:
    if not settings.splitwise_access_token:
        return SplitwiseResult(ok=False, expense_id=None, detail="splitwise_token_missing")

    url = "https://secure.splitwise.com/api/v3.0/create_expense"
    headers = {"Authorization": f"Bearer {settings.splitwise_access_token}"}

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        expense_id = data.get("expenses", [{}])[0].get("id")
        if not expense_id:
            expense_id = f"sw-{int(datetime.now(UTC).timestamp())}"
        return SplitwiseResult(ok=True, expense_id=str(expense_id), detail="posted")
    except Exception as exc:  # noqa: BLE001
        return SplitwiseResult(ok=False, expense_id=None, detail=f"splitwise_error:{exc}")
