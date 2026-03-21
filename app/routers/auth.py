from __future__ import annotations

from fastapi import APIRouter, Query

from app.services import splitwise_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/splitwise/start")
def splitwise_start() -> dict[str, str]:
    return {"authorize_url": splitwise_service.authorization_url()}


@router.get("/splitwise/callback")
def splitwise_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
) -> dict[str, str | bool | None]:
    if not code:
        return {"ok": False, "detail": "Missing authorization code", "state": state}

    # OAuth token exchange is intentionally deferred in this skeleton.
    return {
        "ok": True,
        "detail": "Received callback code. Implement token exchange in Phase 4.",
        "code_preview": f"{code[:6]}...",
        "state": state,
    }
