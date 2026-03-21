from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app import models
from app.schemas import IosSmsIngestRequest, ReviewSubmitRequest
from app.services.dedupe_service import compute_dedupe_key, normalize_message
from app.services.parser_service import ParseResult


def log_event(
    db: Session,
    *,
    event_type: str,
    payload: dict,
    transaction_id: str | None = None,
) -> None:
    db.add(
        models.EventLog(
            transaction_id=transaction_id,
            event_type=event_type,
            payload_json=json.dumps(payload, ensure_ascii=True),
        )
    )
    db.commit()


def get_transaction_by_dedupe(db: Session, dedupe_key: str) -> models.Transaction | None:
    stmt = select(models.Transaction).where(models.Transaction.dedupe_key == dedupe_key)
    return db.scalar(stmt)


def get_transaction(db: Session, transaction_id: str) -> models.Transaction | None:
    stmt = select(models.Transaction).where(models.Transaction.id == transaction_id)
    return db.scalar(stmt)


def create_transaction(
    db: Session,
    *,
    payload: IosSmsIngestRequest,
    parse_result: ParseResult,
) -> models.Transaction:
    normalized_message = normalize_message(payload.message)
    dedupe_key = compute_dedupe_key(
        sender=payload.sender,
        normalized_message=normalized_message,
        reference_id=parse_result.reference_id,
        amount_minor=parse_result.amount_minor,
        last4=parse_result.last4,
        merchant=parse_result.merchant,
        occurred_at=parse_result.occurred_at,
    )

    status = "needs_review"
    if parse_result.parse_confidence < 0.60 or parse_result.amount_minor is None:
        status = "parse_failed"

    tx = models.Transaction(
        source="ios_sms",
        status=status,
        raw_message=payload.message,
        sender=payload.sender,
        contact_name=payload.contact_name,
        received_at=payload.received_at,
        occurred_at=parse_result.occurred_at,
        amount_minor=parse_result.amount_minor,
        currency=parse_result.currency,
        merchant=parse_result.merchant,
        channel=parse_result.channel,
        account_label=parse_result.account_label,
        last4=parse_result.last4,
        reference_id=parse_result.reference_id,
        parse_confidence=parse_result.parse_confidence,
        dedupe_key=dedupe_key,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


def update_transaction_status(
    db: Session,
    *,
    transaction: models.Transaction,
    status: str,
    notes: str | None = None,
) -> models.Transaction:
    transaction.status = status
    if notes:
        transaction.notes = notes
    transaction.updated_at = datetime.now(UTC)
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def save_draft(
    db: Session,
    *,
    transaction: models.Transaction,
    payload: ReviewSubmitRequest,
) -> models.DraftAction:
    draft = models.DraftAction(
        transaction_id=transaction.id,
        draft_payload_json=payload.model_dump_json(),
        draft_status="open",
    )
    transaction.status = "draft"
    db.add(draft)
    db.add(transaction)
    db.commit()
    db.refresh(draft)
    return draft


def list_open_drafts(db: Session, limit: int = 25) -> list[models.DraftAction]:
    stmt = (
        select(models.DraftAction)
        .where(models.DraftAction.draft_status == "open")
        .order_by(desc(models.DraftAction.updated_at))
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def list_pending_transactions(db: Session, limit: int = 25) -> list[models.Transaction]:
    stmt = (
        select(models.Transaction)
        .where(models.Transaction.status.in_(["needs_review", "parse_failed", "draft"]))
        .order_by(desc(models.Transaction.updated_at))
        .limit(limit)
    )
    return list(db.scalars(stmt).all())
