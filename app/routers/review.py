from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import ActionResponse, ReviewSubmitRequest
from app.services import splitwise_service, transaction_service

router = APIRouter(prefix="/review", tags=["review"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/{transaction_id}", response_class=HTMLResponse)
def review_form(transaction_id: str, request: Request, db: Session = Depends(get_db)):
    tx = transaction_service.get_transaction(db, transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    groups = list(db.scalars(select(models.GroupCache).limit(25)).all())
    return templates.TemplateResponse(
        request=request,
        name="review_form.html",
        context={
            "transaction": tx,
            "groups": groups,
        },
    )


@router.post("/{transaction_id}", response_model=ActionResponse)
def submit_review(
    transaction_id: str,
    payload: ReviewSubmitRequest,
    db: Session = Depends(get_db),
) -> ActionResponse:
    tx = transaction_service.get_transaction(db, transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if payload.action == "ignore":
        tx = transaction_service.update_transaction_status(
            db,
            transaction=tx,
            status="ignored",
            notes=payload.notes,
        )
        transaction_service.log_event(
            db,
            transaction_id=tx.id,
            event_type="review_ignored",
            payload=payload.model_dump(),
        )
        return ActionResponse(ok=True, status=tx.status, detail="Ignored", transaction_id=tx.id)

    if payload.action == "manually_done":
        tx = transaction_service.update_transaction_status(
            db,
            transaction=tx,
            status="ignored",
            notes="manually_done",
        )
        draft = models.DraftAction(
            transaction_id=tx.id,
            draft_payload_json=payload.model_dump_json(),
            draft_status="manually_done",
        )
        db.add(draft)
        db.commit()
        transaction_service.log_event(
            db,
            transaction_id=tx.id,
            event_type="review_manually_done",
            payload=payload.model_dump(),
        )
        return ActionResponse(
            ok=True,
            status=tx.status,
            detail="Marked manually done",
            transaction_id=tx.id,
        )

    if payload.action == "draft":
        transaction_service.save_draft(db, transaction=tx, payload=payload)
        transaction_service.log_event(
            db,
            transaction_id=tx.id,
            event_type="review_drafted",
            payload=payload.model_dump(),
        )
        return ActionResponse(
            ok=True,
            status="draft",
            detail="Saved as draft",
            transaction_id=tx.id,
        )

    if tx.amount_minor is None:
        transaction_service.save_draft(db, transaction=tx, payload=payload)
        return ActionResponse(
            ok=False,
            status="draft",
            detail="Amount missing; saved as draft",
            transaction_id=tx.id,
        )

    splitwise_payload = {
        "description": payload.description or tx.merchant or "Shared expense",
        "cost": tx.amount_minor / 100,
        "currency_code": tx.currency,
        "group_id": payload.group_id,
        "split_mode": payload.split_mode,
        "participant_ids": payload.participant_ids,
        "notes": payload.notes,
        "custom_amounts_minor": payload.custom_amounts_minor,
    }

    result = splitwise_service.create_expense(splitwise_payload)

    if result.ok:
        tx.status = "posted"
        tx.splitwise_expense_id = result.expense_id
        tx.posted_at = datetime.now(UTC)
        tx.updated_at = datetime.now(UTC)
        db.add(tx)
        db.commit()

        transaction_service.log_event(
            db,
            transaction_id=tx.id,
            event_type="splitwise_posted",
            payload={"expense_id": result.expense_id},
        )

        return ActionResponse(
            ok=True,
            status="posted",
            detail=f"Posted to Splitwise: {result.expense_id}",
            transaction_id=tx.id,
        )

    transaction_service.save_draft(db, transaction=tx, payload=payload)
    transaction_service.log_event(
        db,
        transaction_id=tx.id,
        event_type="splitwise_failed",
        payload={"detail": result.detail},
    )
    return ActionResponse(
        ok=False,
        status="draft",
        detail="Splitwise post failed; saved as draft",
        transaction_id=tx.id,
    )
