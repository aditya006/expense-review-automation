from __future__ import annotations

import hashlib
from datetime import datetime


def normalize_message(message: str) -> str:
    return " ".join(message.strip().split())


def compute_dedupe_key(
    *,
    sender: str,
    normalized_message: str,
    reference_id: str | None,
    amount_minor: int | None,
    last4: str | None,
    merchant: str | None,
    occurred_at: datetime | None,
) -> str:
    sender_norm = sender.strip().lower()

    if reference_id:
        return f"ref:{sender_norm}:{reference_id.strip().lower()}"

    if amount_minor is not None and last4 and merchant and occurred_at:
        minute_bucket = occurred_at.strftime("%Y%m%d%H%M")
        merchant_norm = " ".join(merchant.lower().split())
        return f"combo:{sender_norm}:{amount_minor}:{last4}:{merchant_norm}:{minute_bucket}"

    msg_hash = hashlib.sha256(normalized_message.encode("utf-8")).hexdigest()
    return f"hash:{sender_norm}:{msg_hash}"
