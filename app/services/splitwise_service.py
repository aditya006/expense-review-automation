from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.services import secret_store_service

settings = get_settings()


@dataclass
class SplitwiseResult:
    ok: bool
    expense_id: str | None
    detail: str


def authorization_url(state_token: str) -> str:
    return (
        "https://secure.splitwise.com/oauth/authorize"
        f"?response_type=code&client_id={settings.splitwise_client_id}"
        f"&redirect_uri={settings.splitwise_redirect_uri}&state={state_token}"
    )


def exchange_code_for_token(code: str) -> str:
    if not settings.splitwise_client_id or not settings.splitwise_client_secret:
        raise RuntimeError("Splitwise client credentials are not configured")

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": settings.splitwise_client_id,
        "client_secret": settings.splitwise_client_secret,
        "redirect_uri": settings.splitwise_redirect_uri,
    }

    response = httpx.post(
        "https://secure.splitwise.com/oauth/token",
        data=payload,
        timeout=10.0,
    )
    response.raise_for_status()
    data = response.json()

    token = data.get("access_token")
    if not token:
        raise RuntimeError("Splitwise token exchange did not return access_token")
    return str(token)


def save_access_token(db: Session, token: str) -> None:
    secret_store_service.set_secret(db, key="splitwise_access_token", value=token)


def _access_token(db: Session) -> str | None:
    token = secret_store_service.get_secret(db, key="splitwise_access_token")
    if token:
        return token
    if settings.splitwise_access_token:
        return settings.splitwise_access_token
    return None


def _headers(db: Session) -> dict[str, str]:
    token = _access_token(db)
    if not token:
        raise RuntimeError("Splitwise access token is missing")
    return {"Authorization": f"Bearer {token}"}


def fetch_current_user(db: Session) -> dict[str, Any]:
    response = httpx.get(
        "https://secure.splitwise.com/api/v3.0/get_current_user",
        headers=_headers(db),
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


def fetch_groups(db: Session) -> list[dict[str, Any]]:
    response = httpx.get(
        "https://secure.splitwise.com/api/v3.0/get_groups",
        headers=_headers(db),
        timeout=10.0,
    )
    response.raise_for_status()
    data = response.json()
    groups = data.get("groups", [])
    if not isinstance(groups, list):
        return []
    return groups


def create_expense(db: Session, payload: dict[str, Any]) -> SplitwiseResult:
    try:
        response = httpx.post(
            "https://secure.splitwise.com/api/v3.0/create_expense",
            json=payload,
            headers=_headers(db),
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

        expense_id = data.get("expenses", [{}])[0].get("id")
        if not expense_id:
            return SplitwiseResult(ok=False, expense_id=None, detail="splitwise_missing_expense_id")

        return SplitwiseResult(ok=True, expense_id=str(expense_id), detail="posted")
    except Exception as exc:  # noqa: BLE001
        return SplitwiseResult(ok=False, expense_id=None, detail=f"splitwise_error:{exc}")
