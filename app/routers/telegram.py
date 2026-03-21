from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import ActionResponse, ReviewSubmitRequest, TelegramWebhookRequest
from app.services import transaction_service

router = APIRouter(prefix="/telegram", tags=["telegram"])


def _list_drafts_text(db: Session) -> str:
    drafts = transaction_service.list_open_drafts(db)
    if not drafts:
        return "No open drafts."

    lines = ["Open drafts:"]
    for draft in drafts:
        lines.append(f"- {draft.transaction_id}")
    return "\n".join(lines)


def _list_pending_text(db: Session) -> str:
    pending = transaction_service.list_pending_transactions(db)
    if not pending:
        return "No pending transactions."

    lines = ["Pending transactions:"]
    for tx in pending:
        lines.append(f"- {tx.id} ({tx.status})")
    return "\n".join(lines)


@router.post("/webhook")
def telegram_webhook(
    update: TelegramWebhookRequest,
    db: Session = Depends(get_db),
) -> dict[str, str | bool]:
    if update.message:
        text = (update.message.get("text") or "").strip()
        if text == "/start":
            return {"ok": True, "message": "Expense bot ready. Use /pending or /drafts."}
        if text == "/help":
            return {
                "ok": True,
                "message": "Commands: /start, /pending, /drafts, /help",
            }
        if text == "/pending":
            return {"ok": True, "message": _list_pending_text(db)}
        if text == "/drafts":
            return {"ok": True, "message": _list_drafts_text(db)}
        return {"ok": True, "message": "Unsupported command."}

    if update.callback_query:
        callback_data = (update.callback_query.get("data") or "").strip()
        parts = callback_data.split("|")
        if len(parts) < 3 or parts[0] != "tx":
            raise HTTPException(status_code=400, detail="Invalid callback payload")

        transaction_id = parts[1]
        action = parts[2]

        tx = transaction_service.get_transaction(db, transaction_id)
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found")

        if action == "me_only":
            transaction_service.update_transaction_status(
                db,
                transaction=tx,
                status="ignored",
                notes="marked_me_only",
            )
            transaction_service.log_event(
                db,
                transaction_id=tx.id,
                event_type="telegram_action",
                payload={"action": action},
            )
            return {"ok": True, "message": "Marked as me-only. No Splitwise expense created."}

        if action == "ignore":
            transaction_service.update_transaction_status(
                db,
                transaction=tx,
                status="ignored",
                notes="ignored_from_telegram",
            )
            transaction_service.log_event(
                db,
                transaction_id=tx.id,
                event_type="telegram_action",
                payload={"action": action},
            )
            return {"ok": True, "message": "Ignored."}

        if action == "draft":
            draft_payload = ReviewSubmitRequest(action="draft")
            transaction_service.save_draft(db, transaction=tx, payload=draft_payload)
            transaction_service.log_event(
                db,
                transaction_id=tx.id,
                event_type="telegram_action",
                payload={"action": action},
            )
            return {
                "ok": True,
                "message": "Saved as draft. You can finish it later from /drafts.",
            }

        if action == "choose_group":
            groups = db.scalars(select(models.GroupCache).limit(10)).all()
            if not groups:
                return {
                    "ok": True,
                    "message": "No cached groups yet. Open form to choose manually.",
                }
            names = ", ".join(group.group_name for group in groups)
            return {"ok": True, "message": f"Likely groups: {names}"}

        return {"ok": True, "message": f"Unhandled action: {action}"}

    return {"ok": True, "message": "No-op update"}


@router.get("/pending", response_model=list[ActionResponse])
def pending_actions(db: Session = Depends(get_db)) -> list[ActionResponse]:
    pending = transaction_service.list_pending_transactions(db)
    return [
        ActionResponse(
            ok=True,
            status=tx.status,
            detail=tx.merchant or "",
            transaction_id=tx.id,
        )
        for tx in pending
    ]
