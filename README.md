# Expense Review Automation

Personal iPhone SMS to Telegram review workflow with optional Splitwise posting.

## Stack
- FastAPI
- SQLite (v1)
- Telegram Bot API
- Splitwise API (OAuth + expense create)

## Quick Start

1. Create a virtualenv and install deps:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

2. Configure environment:
```bash
cp .env.example .env
```

3. Run the app:
```bash
uvicorn app.main:app --reload
```

4. Run tests:
```bash
pytest
```

5. Validate setup completeness:
```bash
python scripts/check_setup.py
```

## Secure Production Settings
Set these before `APP_ENV=production`:
- `INGEST_API_KEY` (required in ingest shortcut header)
- `TELEGRAM_WEBHOOK_SECRET` (required in Telegram webhook registration)
- `SIGNING_SECRET` (non-default, at least 16 chars)
- `APP_BASE_URL` (`https://...`)
- `ALLOWED_HOSTS` (comma-separated exact hostnames)

In production mode:
- startup fails if critical security settings are missing
- docs (`/docs`, `/redoc`, `/openapi.json`) are disabled by default

## Main Endpoints
- `POST /ingest/ios-sms` (requires `X-Ingest-Key` in secure mode)
- `POST /telegram/webhook` (verifies Telegram secret header)
- `GET /review/{transaction_id}?t=<signed_token>`
- `POST /review/{transaction_id}?t=<signed_token>`
- `GET /auth/splitwise/start`
- `GET /auth/splitwise/callback`
- `POST /auth/splitwise/sync-groups` (admin key required)
- `GET /admin/transactions/{id}` (admin key required)
- `GET /admin/drafts` (admin key required)
- `POST /admin/reparse/{transaction_id}` (admin key required)
- `GET /health`

## iPhone Shortcut Request Headers
For `POST /ingest/ios-sms`, include:
- `Content-Type: application/json`
- `X-Ingest-Key: <INGEST_API_KEY>`

## Notes
- No Splitwise post happens without explicit user action.
- Drafts are retained on errors.
- Dedupe logic prevents duplicate prompts for repeated SMS alerts.
- Splitwise token is stored encrypted in SQLite using `SIGNING_SECRET` derived crypto key.
