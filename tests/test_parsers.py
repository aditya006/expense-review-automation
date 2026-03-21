from __future__ import annotations

from datetime import UTC, datetime

from app.services.parser_service import parse_sms


def test_hdfc_card_message_parses_fields() -> None:
    result = parse_sms(
        sender="HDFCBK",
        message="Rs.850 spent on HDFC Bank Card xx1234 at ZEPTO on 20-03-2026 14:04 Ref ABC123",
        received_at=datetime(2026, 3, 20, 14, 5, tzinfo=UTC),
    )

    assert result.is_transaction is True
    assert result.amount_minor == 85000
    assert result.merchant == "Zepto"
    assert result.last4 == "1234"
    assert result.reference_id == "ABC123"
    assert result.channel == "card"
    assert result.parse_confidence >= 0.85


def test_otp_message_is_ignored() -> None:
    result = parse_sms(
        sender="HDFCBK",
        message="Your OTP for login is 123456. Do not share this OTP.",
        received_at=datetime.now(UTC),
    )

    assert result.is_transaction is False
    assert result.ignore_reason == "ignore_rule_match"
