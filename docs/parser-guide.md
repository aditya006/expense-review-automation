# Parser Guide

## Scope
Parse bank/card spend SMS into structured transaction data for review and optional Splitwise posting.

## Parsing Strategy
Use bank-specific regex rules first, then generic fallback rules.

## Parser Pipeline
1. Normalize SMS text (trim whitespace, collapse repeated spaces, preserve original raw text)
2. Identify sender family (`HDFCBK`, `ICICIB`, `SBICRD`, `AXISBK`)
3. Apply sender-specific parser
4. Apply generic amount extractor
5. Apply merchant extractor
6. Infer payment channel
7. Extract reference ID and last4
8. Compute confidence
9. Return parsed object

## Example Parsed Object
```json
{
  "amount_minor": 85000,
  "currency": "INR",
  "merchant": "Zepto",
  "channel": "card",
  "last4": "1234",
  "reference_id": "ABC123",
  "occurred_at": "2026-03-20T14:04:00+05:30",
  "parse_confidence": 0.92
}
```

## Sender Rules
Create one parser module per sender family:
- `hdfc.py`
- `icici.py`
- `sbi_card.py`
- `axis.py`
- `generic.py`

## Ignore Rules
Reject messages matching:
- OTP/password
- EMI reminder
- bill due
- statement ready
- account credited
- cashback received
- loan alert
- marketing/promotional copy

## Deduplication Rules
Priority:
1. sender + reference ID
2. sender + amount + last4 + merchant + minute bucket
3. full normalized SMS hash

## Confidence Thresholds
- `>= 0.85`: auto-send normal Telegram prompt
- `0.60 - 0.84`: send prompt with “please verify”
- `< 0.60`: mark as `parse_failed` and route to manual form

## Fixture Requirements
Create anonymized SMS fixtures for:
- UPI spends
- card spends
- duplicate alerts
- failed parses
- non-transaction bank messages

## Testing Targets
- parser tests per bank sender
- dedupe key generation
- status transitions
