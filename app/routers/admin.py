from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.security import verify_admin_api_key
from app.services import parser_service, transaction_service

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(verify_admin_api_key)])


@router.get("/transactions/{transaction_id}")
def get_transaction(transaction_id: str, db: Session = Depends(get_db)) -> dict:
    tx = transaction_service.get_transaction(db, transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return {
        "id": tx.id,
        "status": tx.status,
        "sender": tx.sender,
        "merchant": tx.merchant,
        "amount_minor": tx.amount_minor,
        "channel": tx.channel,
        "last4": tx.last4,
        "reference_id": tx.reference_id,
        "parse_confidence": tx.parse_confidence,
        "created_at": tx.created_at.isoformat(),
        "updated_at": tx.updated_at.isoformat(),
    }


@router.get("/drafts")
def get_drafts(db: Session = Depends(get_db)) -> list[dict[str, str]]:
    drafts = transaction_service.list_open_drafts(db, limit=100)
    return [
        {
            "id": draft.id,
            "transaction_id": draft.transaction_id,
            "draft_status": draft.draft_status,
            "updated_at": draft.updated_at.isoformat(),
        }
        for draft in drafts
    ]


@router.post("/reparse/{transaction_id}")
def reparse_transaction(
    transaction_id: str,
    db: Session = Depends(get_db),
) -> dict[str, str | float]:
    tx = transaction_service.get_transaction(db, transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    parsed = parser_service.parse_sms(
        sender=tx.sender,
        message=tx.raw_message,
        received_at=tx.received_at,
    )
    if not parsed.is_transaction:
        tx.status = "ignored"
        db.add(tx)
        db.commit()
        return {"ok": "true", "status": "ignored", "parse_confidence": 0.0}

    tx.amount_minor = parsed.amount_minor
    tx.currency = parsed.currency
    tx.merchant = parsed.merchant
    tx.channel = parsed.channel
    tx.last4 = parsed.last4
    tx.reference_id = parsed.reference_id
    tx.occurred_at = parsed.occurred_at
    tx.parse_confidence = parsed.parse_confidence
    tx.status = (
        "needs_review"
        if parsed.parse_confidence >= 0.60 and parsed.amount_minor
        else "parse_failed"
    )

    db.add(tx)
    db.commit()

    transaction_service.log_event(
        db,
        transaction_id=tx.id,
        event_type="admin_reparse",
        payload={"status": tx.status, "parse_confidence": tx.parse_confidence},
    )

    return {
        "ok": "true",
        "status": tx.status,
        "parse_confidence": tx.parse_confidence or 0.0,
    }
