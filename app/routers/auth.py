from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.security import verify_admin_api_key
from app.services import link_signing_service, splitwise_service, transaction_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/splitwise/start")
def splitwise_start() -> dict[str, str]:
    state_token = link_signing_service.create_oauth_state_token()
    return {"authorize_url": splitwise_service.authorization_url(state_token)}


@router.get("/splitwise/callback")
def splitwise_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, str | bool | None]:
    if not code:
        return {"ok": False, "detail": "Missing authorization code", "state": state}

    if not state or not link_signing_service.verify_oauth_state_token(state):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    try:
        access_token = splitwise_service.exchange_code_for_token(code)
        splitwise_service.save_access_token(db, access_token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail=f"Splitwise token exchange failed: {exc}",
        ) from exc

    transaction_service.log_event(
        db,
        event_type="splitwise_auth_success",
        payload={"token_preview": f"{access_token[:6]}..."},
    )

    return {
        "ok": True,
        "detail": "Splitwise authorization completed",
        "state": state,
    }


@router.post("/splitwise/sync-groups")
def splitwise_sync_groups(
    _: None = Depends(verify_admin_api_key),
    db: Session = Depends(get_db),
) -> dict[str, str | int]:
    try:
        groups = splitwise_service.fetch_groups(db)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Splitwise group sync failed: {exc}") from exc

    for group in groups:
        members = group.get("members", [])
        transaction_service.upsert_group_cache(
            db,
            group_id=str(group.get("id")),
            group_name=str(group.get("name", "Unnamed Group")),
            members_json=json.dumps(members),
        )

    transaction_service.log_event(
        db,
        event_type="splitwise_groups_synced",
        payload={"count": len(groups)},
    )
    return {"ok": True, "count": len(groups), "detail": "Groups synced"}
