from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

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
    draft = db.scalar(
        select(models.DraftAction)
        .where(
            models.DraftAction.transaction_id == transaction.id,
            models.DraftAction.draft_status == "open",
        )
        .order_by(desc(models.DraftAction.updated_at))
    )
    if draft:
        draft.draft_payload_json = payload.model_dump_json()
    else:
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


def list_all_drafts(db: Session, limit: int = 100) -> list[models.DraftAction]:
    stmt = select(models.DraftAction).order_by(desc(models.DraftAction.updated_at)).limit(limit)
    return list(db.scalars(stmt).all())


def list_pending_transactions(db: Session, limit: int = 25) -> list[models.Transaction]:
    stmt = (
        select(models.Transaction)
        .where(models.Transaction.status.in_(["needs_review", "parse_failed", "draft"]))
        .order_by(desc(models.Transaction.updated_at))
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def _has_unsettled_balance(members_json: str) -> bool:
    try:
        members = json.loads(members_json)
    except json.JSONDecodeError:
        return False

    if not isinstance(members, list):
        return False

    for member in members:
        if not isinstance(member, dict):
            continue
        balances = member.get("balance")
        if not isinstance(balances, list):
            continue
        for balance in balances:
            if not isinstance(balance, dict):
                continue
            raw_amount = balance.get("amount", "0")
            try:
                amount = Decimal(str(raw_amount))
            except (InvalidOperation, TypeError, ValueError):
                continue
            if amount != 0:
                return True
    return False


def list_groups_with_unsettled_balance(
    db: Session,
    *,
    limit: int = 10,
) -> list[models.GroupCache]:
    stmt = select(models.GroupCache).order_by(desc(models.GroupCache.updated_at))
    groups = list(db.scalars(stmt).all())
    unsettled = [group for group in groups if _has_unsettled_balance(group.members_json)]
    return unsettled[:limit]


def upsert_group_cache(db: Session, *, group_id: str, group_name: str, members_json: str) -> None:
    existing = db.scalar(select(models.GroupCache).where(models.GroupCache.group_id == group_id))
    if existing:
        existing.group_name = group_name
        existing.members_json = members_json
        db.add(existing)
    else:
        db.add(
            models.GroupCache(
                group_id=group_id,
                group_name=group_name,
                members_json=members_json,
            )
        )
    db.commit()
