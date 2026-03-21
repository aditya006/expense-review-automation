from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.parsers import axis, generic, hdfc, icici, sbi_card


@dataclass
class ParseResult:
    is_transaction: bool
    ignore_reason: str | None
    amount_minor: int | None
    currency: str
    merchant: str | None
    channel: str
    last4: str | None
    account_label: str | None
    reference_id: str | None
    occurred_at: datetime | None
    parse_confidence: float


def _family_for_sender(sender: str) -> str:
    s = sender.strip().upper()
    if s.startswith("HDFC") or s.startswith("HDFCBK"):
        return "hdfc"
    if s.startswith("ICICI") or s.startswith("ICICIB"):
        return "icici"
    if s.startswith("SBI") or s.startswith("SBICRD"):
        return "sbi_card"
    if s.startswith("AXIS") or s.startswith("AXISBK"):
        return "axis"
    return "generic"


def _apply_sender_parser(sender_family: str, message: str) -> dict[str, str | int | float | None]:
    if sender_family == "hdfc":
        return hdfc.parse(message)
    if sender_family == "icici":
        return icici.parse(message)
    if sender_family == "sbi_card":
        return sbi_card.parse(message)
    if sender_family == "axis":
        return axis.parse(message)

    return {
        "amount_minor": generic.parse_amount_minor(message),
        "merchant": generic.parse_merchant(message),
        "last4": generic.parse_last4(message),
        "reference_id": generic.parse_reference_id(message),
        "channel": generic.infer_channel(message),
        "account_label": None,
    }


def parse_sms(*, sender: str, message: str, received_at: datetime) -> ParseResult:
    if generic.is_ignored_message(message):
        return ParseResult(
            is_transaction=False,
            ignore_reason="ignore_rule_match",
            amount_minor=None,
            currency="INR",
            merchant=None,
            channel="unknown",
            last4=None,
            account_label=None,
            reference_id=None,
            occurred_at=None,
            parse_confidence=0.0,
        )

    sender_family = _family_for_sender(sender)
    parsed = _apply_sender_parser(sender_family, message)

    amount_minor = parsed.get("amount_minor")  # type: ignore[assignment]
    merchant = parsed.get("merchant")  # type: ignore[assignment]
    channel = (parsed.get("channel") or "unknown")  # type: ignore[assignment]
    reference_id = parsed.get("reference_id")  # type: ignore[assignment]
    last4 = parsed.get("last4")  # type: ignore[assignment]
    account_label = parsed.get("account_label")  # type: ignore[assignment]
    occurred_at = generic.parse_occurred_at(message, received_at)

    confidence = 0.35
    if amount_minor is not None:
        confidence += 0.35
    if merchant:
        confidence += 0.15
    if channel and channel != "unknown":
        confidence += 0.10
    if reference_id or last4:
        confidence += 0.05

    confidence = min(confidence, 0.99)

    return ParseResult(
        is_transaction=True,
        ignore_reason=None,
        amount_minor=amount_minor,
        currency="INR",
        merchant=merchant,
        channel=channel,
        last4=last4,
        account_label=account_label,
        reference_id=reference_id,
        occurred_at=occurred_at,
        parse_confidence=confidence,
    )
