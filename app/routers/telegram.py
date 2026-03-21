from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import ActionResponse, ReviewSubmitRequest, TelegramWebhookRequest
from app.security import enforce_single_user_chat, verify_telegram_webhook_secret
from app.services import (
    link_signing_service,
    splitwise_service,
    telegram_service,
    transaction_service,
)

router = APIRouter(prefix="/telegram", tags=["telegram"])


def _list_drafts_text(db: Session) -> str:
    drafts = transaction_service.list_open_drafts(db)
    if not drafts:
        return "No open drafts."

    lines = ["Open drafts:"]
    for draft in drafts:
        link = link_signing_service.build_review_link(draft.transaction_id)
        lines.append(f"- {draft.transaction_id} -> {link}")
    return "\n".join(lines)


def _list_pending_text(db: Session) -> str:
    pending = transaction_service.list_pending_transactions(db)
    if not pending:
        return "No pending transactions."

    lines = ["Pending transactions:"]
    for tx in pending:
        link = link_signing_service.build_review_link(tx.id)
        lines.append(f"- {tx.id} ({tx.status}) -> {link}")
    return "\n".join(lines)


def _parse_callback_data(data: str) -> tuple[str, str | None, str | None]:
    parts = data.split("|")
    if len(parts) < 3 or parts[0] != "tx":
        raise HTTPException(status_code=400, detail="Invalid callback payload")
    tx_id = parts[1]
    action = parts[2]
    arg = parts[3] if len(parts) > 3 else None
    return tx_id, action, arg


def _groups_keyboard(tx_id: str, groups: list[models.GroupCache]) -> dict[str, Any]:
    rows: list[list[dict[str, str]]] = []
    for group in groups[:10]:
        rows.append(
            [
                {
                    "text": group.group_name,
                    "callback_data": f"tx|{tx_id}|group|{group.group_id}",
                }
            ]
        )
    return {"inline_keyboard": rows}


def _group_action_keyboard(tx_id: str, group_id: str) -> dict[str, Any]:
    review_link = link_signing_service.build_review_link(tx_id)
    return {
        "inline_keyboard": [
            [
                {
                    "text": "Split All Equally",
                    "callback_data": f"tx|{tx_id}|split_all|{group_id}",
                },
                {"text": "Draft", "callback_data": f"tx|{tx_id}|draft"},
            ],
            [
                {
                    "text": "Open Form",
                    "url": review_link,
                }
            ],
        ]
    }


def _extract_chat_id(update: TelegramWebhookRequest) -> str | None:
    if update.message and isinstance(update.message.get("chat"), dict):
        chat_id = update.message["chat"].get("id")
        return str(chat_id) if chat_id is not None else None

    if update.callback_query and isinstance(update.callback_query.get("message"), dict):
        chat = update.callback_query["message"].get("chat")
        if isinstance(chat, dict) and chat.get("id") is not None:
            return str(chat["id"])

    return None


@router.post("/webhook")
def telegram_webhook(
    update: TelegramWebhookRequest,
    request: Request,
    _: None = Depends(verify_telegram_webhook_secret),
    db: Session = Depends(get_db),
) -> dict[str, str | bool]:
    payload = update.model_dump(exclude_none=True)
    enforce_single_user_chat(request, payload)

    chat_id = _extract_chat_id(update)

    if update.message:
        text = (update.message.get("text") or "").strip()
        if text == "/start":
            msg = "Expense bot ready. Use /pending or /drafts."
        elif text == "/help":
            msg = "Commands: /start, /pending, /drafts, /help"
        elif text == "/pending":
            msg = _list_pending_text(db)
        elif text == "/drafts":
            msg = _list_drafts_text(db)
        else:
            msg = "Unsupported command."

        telegram_service.send_text_message(text=msg, chat_id=chat_id)
        return {"ok": True, "message": msg}

    if update.callback_query:
        callback_query = update.callback_query
        callback_data = (callback_query.get("data") or "").strip()
        callback_id = str(callback_query.get("id", ""))

        transaction_id, action, arg = _parse_callback_data(callback_data)
        tx = transaction_service.get_transaction(db, transaction_id)
        if not tx:
            telegram_service.answer_callback_query(callback_id, text="Transaction not found")
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
            telegram_service.answer_callback_query(callback_id, text="Marked as me-only")
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
            telegram_service.answer_callback_query(callback_id, text="Ignored")
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
            telegram_service.answer_callback_query(callback_id, text="Saved as draft")
            return {
                "ok": True,
                "message": "Saved as draft. You can finish it later from /drafts.",
            }

        if action == "choose_group":
            groups = list(db.scalars(select(models.GroupCache).limit(10)).all())
            if not groups:
                review_link = link_signing_service.build_review_link(tx.id)
                msg = f"No cached groups yet. Open form to choose manually: {review_link}"
                telegram_service.send_text_message(text=msg, chat_id=chat_id)
                telegram_service.answer_callback_query(callback_id, text="No groups cached")
                return {"ok": True, "message": msg}

            telegram_service.send_text_message(
                text="Choose a group:",
                chat_id=chat_id,
                reply_markup=_groups_keyboard(tx.id, groups),
            )
            telegram_service.answer_callback_query(callback_id, text="Select group")
            return {"ok": True, "message": "Group options sent"}

        if action == "group":
            if not arg:
                raise HTTPException(status_code=400, detail="Missing group id")

            group = db.scalar(select(models.GroupCache).where(models.GroupCache.group_id == arg))
            if not group:
                raise HTTPException(status_code=404, detail="Group not found")

            tx.suggested_group_id = group.group_id
            tx.suggested_group_name = group.group_name
            db.add(tx)
            db.commit()

            telegram_service.send_text_message(
                text=f"Use this expense for {group.group_name}?",
                chat_id=chat_id,
                reply_markup=_group_action_keyboard(tx.id, group.group_id),
            )
            telegram_service.answer_callback_query(callback_id, text="Group selected")
            return {"ok": True, "message": f"Group selected: {group.group_name}"}

        if action == "split_all":
            if not arg:
                raise HTTPException(status_code=400, detail="Missing group id")

            group = db.scalar(select(models.GroupCache).where(models.GroupCache.group_id == arg))
            if not group:
                raise HTTPException(status_code=404, detail="Group not found")

            if tx.amount_minor is None:
                draft_payload = ReviewSubmitRequest(action="draft", group_id=group.group_id)
                transaction_service.save_draft(db, transaction=tx, payload=draft_payload)
                telegram_service.answer_callback_query(callback_id, text="Saved as draft")
                return {"ok": False, "message": "Amount missing; saved as draft"}

            members = json.loads(group.members_json)
            participants = [str(member.get("id", member)) for member in members]
            splitwise_payload = {
                "description": tx.merchant or "Shared expense",
                "cost": tx.amount_minor / 100,
                "currency_code": tx.currency,
                "group_id": group.group_id,
                "split_mode": "equal",
                "participant_ids": participants,
            }

            result = splitwise_service.create_expense(db, splitwise_payload)
            if result.ok:
                tx.status = "posted"
                tx.splitwise_expense_id = result.expense_id
                tx.posted_at = datetime.now(UTC)
                db.add(tx)
                db.commit()
                msg = (
                    f"Posted to Splitwise: Rs {tx.amount_minor / 100:.2f} in "
                    f"{group.group_name}."
                )
                telegram_service.send_text_message(text=msg, chat_id=chat_id)
                telegram_service.answer_callback_query(callback_id, text="Posted")
                return {"ok": True, "message": msg}

            draft_payload = ReviewSubmitRequest(action="draft", group_id=group.group_id)
            transaction_service.save_draft(db, transaction=tx, payload=draft_payload)
            msg = "Could not post to Splitwise. Transaction saved as draft."
            telegram_service.send_text_message(text=msg, chat_id=chat_id)
            telegram_service.answer_callback_query(callback_id, text="Saved as draft")
            return {"ok": False, "message": msg}

        telegram_service.answer_callback_query(callback_id, text="Unhandled action")
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
