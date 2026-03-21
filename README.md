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
pip install -e .[dev]
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

## Initial Endpoints
- `POST /ingest/ios-sms`
- `POST /telegram/webhook`
- `GET /review/{transaction_id}`
- `POST /review/{transaction_id}`
- `GET /auth/splitwise/start`
- `GET /auth/splitwise/callback`
- `GET /health`

## Notes
- No Splitwise post happens without explicit user action.
- Drafts are retained on errors.
- Dedupe logic prevents duplicate prompts for repeated SMS alerts.
