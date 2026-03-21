from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import IngestResponse, IosSmsIngestRequest
from app.security import verify_ingest_api_key
from app.services import parser_service, telegram_service, transaction_service
from app.services.dedupe_service import compute_dedupe_key, normalize_message

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/ios-sms", response_model=IngestResponse)
def ingest_ios_sms(
    payload: IosSmsIngestRequest,
    _: None = Depends(verify_ingest_api_key),
    db: Session = Depends(get_db),
) -> IngestResponse:
    parse_result = parser_service.parse_sms(
        sender=payload.sender,
        message=payload.message,
        received_at=payload.received_at,
    )

    if not parse_result.is_transaction:
        transaction_service.log_event(
            db,
            event_type="ingest_ignored",
            payload={"sender": payload.sender, "reason": parse_result.ignore_reason},
        )
        return IngestResponse(ok=True, status="ignored")

    dedupe_key = compute_dedupe_key(
        sender=payload.sender,
        normalized_message=normalize_message(payload.message),
        reference_id=parse_result.reference_id,
        amount_minor=parse_result.amount_minor,
        last4=parse_result.last4,
        merchant=parse_result.merchant,
        occurred_at=parse_result.occurred_at,
    )

    existing = transaction_service.get_transaction_by_dedupe(db, dedupe_key)
    if existing:
        transaction_service.log_event(
            db,
            transaction_id=existing.id,
            event_type="ingest_duplicate",
            payload={"dedupe_key": dedupe_key},
        )
        return IngestResponse(
            ok=True,
            transaction_id=existing.id,
            status=existing.status,
            duplicate=True,
        )

    tx = transaction_service.create_transaction(db, payload=payload, parse_result=parse_result)
    transaction_service.log_event(
        db,
        transaction_id=tx.id,
        event_type="ingest_stored",
        payload={
            "status": tx.status,
            "parse_confidence": tx.parse_confidence,
            "sender": tx.sender,
        },
    )

    if tx.status in {"needs_review", "parse_failed"}:
        message_id = telegram_service.send_review_prompt(tx)
        tx.telegram_message_id = message_id
        db.add(tx)
        db.commit()

        transaction_service.log_event(
            db,
            transaction_id=tx.id,
            event_type="telegram_prompt_sent",
            payload={"telegram_message_id": message_id, "status": tx.status},
        )

    return IngestResponse(ok=True, transaction_id=tx.id, status=tx.status)
