from __future__ import annotations

import re
from datetime import datetime

IGNORE_PATTERNS = [
    r"\botp\b",
    r"one time password",
    r"\bemi\b",
    r"bill due",
    r"statement",
    r"credited",
    r"cashback",
    r"loan",
    r"promo",
    r"offer",
    r"reward points",
]

_AMOUNT_PATTERNS = [
    re.compile(r"(?:rs\.?|inr)\s*[:.]?\s*([0-9][0-9,]*(?:\.\d{1,2})?)", re.IGNORECASE),
    re.compile(r"debited\s*(?:for|by)?\s*([0-9][0-9,]*(?:\.\d{1,2})?)", re.IGNORECASE),
]

_MERCHANT_PATTERNS = [
    re.compile(r"\bat\s+([A-Za-z0-9&.,\- ]{2,60})", re.IGNORECASE),
    re.compile(r"\bto\s+([A-Za-z0-9&.,\- ]{2,60})", re.IGNORECASE),
]

_LAST4_PATTERNS = [
    re.compile(r"(?:xx|x)?(\d{4})", re.IGNORECASE),
    re.compile(r"ending\s+(\d{4})", re.IGNORECASE),
]

_REF_PATTERNS = [
    re.compile(
        r"(?:ref(?:erence)?(?:\s*id|\s*no\.?)?|utr|txn(?:\s*id)?)\s*[:\-]?\s*([A-Za-z0-9\-]{4,})",
        re.IGNORECASE,
    ),
]

_DATE_PATTERNS = [
    re.compile(r"(\d{2})[-/](\d{2})[-/](\d{4})\s*(\d{2}):(\d{2})"),
    re.compile(r"(\d{2})[-/](\d{2})[-/](\d{4})"),
]


def is_ignored_message(message: str) -> bool:
    lowered = message.lower()
    return any(re.search(pattern, lowered) for pattern in IGNORE_PATTERNS)


def parse_amount_minor(message: str) -> int | None:
    for pattern in _AMOUNT_PATTERNS:
        match = pattern.search(message)
        if match:
            value = match.group(1).replace(",", "")
            try:
                return int(round(float(value) * 100))
            except ValueError:
                return None
    return None


def parse_merchant(message: str) -> str | None:
    for pattern in _MERCHANT_PATTERNS:
        match = pattern.search(message)
        if match:
            merchant = " ".join(match.group(1).strip().split())
            merchant = re.sub(r"\bon\b.*$", "", merchant, flags=re.IGNORECASE).strip(" .,")
            if merchant and len(merchant) >= 2:
                return merchant.title()
    return None


def parse_last4(message: str) -> str | None:
    for pattern in _LAST4_PATTERNS:
        match = pattern.search(message)
        if match:
            candidate = match.group(1)
            if len(candidate) == 4:
                return candidate
    return None


def parse_reference_id(message: str) -> str | None:
    for pattern in _REF_PATTERNS:
        match = pattern.search(message)
        if match:
            return match.group(1)
    return None


def infer_channel(message: str) -> str:
    lowered = message.lower()
    if "upi" in lowered:
        return "upi"
    if "card" in lowered or "credit card" in lowered or "debit card" in lowered:
        return "card"
    if "bank" in lowered:
        return "bank"
    return "unknown"


def parse_occurred_at(message: str, fallback: datetime) -> datetime:
    for pattern in _DATE_PATTERNS:
        match = pattern.search(message)
        if not match:
            continue

        try:
            if len(match.groups()) == 5:
                dd, mm, yyyy, hh, minute = match.groups()
                return fallback.replace(
                    year=int(yyyy),
                    month=int(mm),
                    day=int(dd),
                    hour=int(hh),
                    minute=int(minute),
                    second=0,
                )
            dd, mm, yyyy = match.groups()
            return fallback.replace(year=int(yyyy), month=int(mm), day=int(dd), second=0)
        except ValueError:
            continue

    return fallback
