from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
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


def _to_decimal_cost(payload: dict[str, Any]) -> Decimal:
    cost_minor = payload.get("cost_minor")
    if cost_minor is not None:
        return (Decimal(int(cost_minor)) / Decimal("100")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    raw_cost = payload.get("cost")
    try:
        return Decimal(str(raw_cost)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid cost for Splitwise payload") from exc


def _normalize_group_id(group_id: Any) -> int:
    if group_id is None:
        raise ValueError("group_id is required for Splitwise create_expense")

    try:
        return int(str(group_id))
    except (TypeError, ValueError) as exc:
        raise ValueError("group_id must be numeric for Splitwise") from exc


def _base_payload(payload: dict[str, Any]) -> dict[str, Any]:
    amount = _to_decimal_cost(payload)
    out: dict[str, Any] = {
        "description": str(payload.get("description") or "Shared expense"),
        "cost": format(amount, ".2f"),
        "currency_code": str(payload.get("currency_code") or "INR"),
        "group_id": _normalize_group_id(payload.get("group_id")),
    }
    notes = payload.get("notes") or payload.get("details")
    if notes:
        out["details"] = str(notes)
    return out


def _build_equal_group_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out = _base_payload(payload)
    out["split_equally"] = True
    return out


def _normalize_participant_ids(payload: dict[str, Any]) -> list[int]:
    participant_ids: list[int] = []
    seen: set[int] = set()
    for participant in payload.get("participant_ids") or []:
        try:
            pid = int(str(participant))
        except (TypeError, ValueError) as exc:
            raise ValueError("participant_ids must be numeric user IDs") from exc
        if pid in seen:
            continue
        seen.add(pid)
        participant_ids.append(pid)
    return participant_ids


def _current_user_id(db: Session) -> int:
    profile = fetch_current_user(db)
    user = profile.get("user") or profile.get("current_user") or {}
    try:
        return int(user["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("Could not determine Splitwise payer user id") from exc


def _build_share_payload(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    out = _base_payload(payload)
    total_minor = int(_to_decimal_cost(payload) * 100)
    participant_ids = _normalize_participant_ids(payload)
    payer_id = _current_user_id(db)
    if payer_id not in participant_ids:
        participant_ids.append(payer_id)

    if not participant_ids:
        raise ValueError("No participant IDs provided for share split")

    custom_amounts_minor = payload.get("custom_amounts_minor") or {}
    owed_minor_by_user: dict[int, int] = {}

    if custom_amounts_minor:
        for pid in participant_ids:
            raw = custom_amounts_minor.get(str(pid), custom_amounts_minor.get(pid, 0))
            owed_minor_by_user[pid] = int(raw)
        if sum(owed_minor_by_user.values()) != total_minor:
            raise ValueError("custom_amounts_minor does not sum to total expense")
    else:
        per_user = total_minor // len(participant_ids)
        remainder = total_minor % len(participant_ids)
        for idx, pid in enumerate(participant_ids):
            owed_minor_by_user[pid] = per_user + (1 if idx < remainder else 0)

    for idx, pid in enumerate(participant_ids):
        paid_minor = total_minor if pid == payer_id else 0
        out[f"users__{idx}__user_id"] = pid
        out[f"users__{idx}__paid_share"] = format(Decimal(paid_minor) / Decimal("100"), ".2f")
        out[f"users__{idx}__owed_share"] = format(
            Decimal(owed_minor_by_user[pid]) / Decimal("100"),
            ".2f",
        )
    return out


def _prepare_create_payload(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    split_mode = payload.get("split_mode", "equal")
    participant_ids = payload.get("participant_ids") or []
    custom_amounts_minor = payload.get("custom_amounts_minor") or {}

    if split_mode == "equal" and not participant_ids and not custom_amounts_minor:
        return _build_equal_group_payload(payload)
    return _build_share_payload(db, payload)


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
        request_payload = _prepare_create_payload(db, payload)
        response = httpx.post(
            "https://secure.splitwise.com/api/v3.0/create_expense",
            json=request_payload,
            headers=_headers(db),
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

        expense_id = data.get("expenses", [{}])[0].get("id")
        if not expense_id:
            return SplitwiseResult(ok=False, expense_id=None, detail="splitwise_missing_expense_id")

        return SplitwiseResult(ok=True, expense_id=str(expense_id), detail="posted")
    except httpx.HTTPStatusError as exc:
        body = exc.response.text.strip()
        detail = f"splitwise_error:{exc.response.status_code}:{body[:300]}"
        return SplitwiseResult(ok=False, expense_id=None, detail=detail)
    except ValueError as exc:
        return SplitwiseResult(
            ok=False,
            expense_id=None,
            detail=f"splitwise_validation_error:{exc}",
        )
    except Exception as exc:  # noqa: BLE001
        return SplitwiseResult(ok=False, expense_id=None, detail=f"splitwise_error:{exc}")
