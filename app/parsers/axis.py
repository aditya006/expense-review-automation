from __future__ import annotations

from app.parsers import generic


def parse(message: str) -> dict[str, str | int | float | None]:
    return {
        "amount_minor": generic.parse_amount_minor(message),
        "merchant": generic.parse_merchant(message),
        "last4": generic.parse_last4(message),
        "reference_id": generic.parse_reference_id(message),
        "channel": generic.infer_channel(message),
        "account_label": "Axis",
    }
