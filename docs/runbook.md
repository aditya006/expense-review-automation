# Runbook

## Environment Variables
- `APP_ENV` (`development` or `production`)
- `APP_BASE_URL`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`
- `TELEGRAM_CHAT_ID`
- `INGEST_API_KEY`
- `ADMIN_API_KEY`
- `SPLITWISE_CLIENT_ID`
- `SPLITWISE_CLIENT_SECRET`
- `SPLITWISE_REDIRECT_URI`
- `SPLITWISE_ACCESS_TOKEN` (optional fallback)
- `DATABASE_URL`
- `SIGNING_SECRET`
- `LOG_LEVEL`
- `REVIEW_LINK_TTL_SECONDS`
- `SPLITWISE_OAUTH_STATE_TTL_SECONDS`
- `DISABLE_DOCS_IN_PRODUCTION`
- `ALLOWED_HOSTS`

## First-Time Setup (Working End-to-End)
1. Create bot in Telegram and copy token (`TELEGRAM_BOT_TOKEN`).
2. Message your bot once from your Telegram account.
3. Set `TELEGRAM_CHAT_ID` to your chat ID.
4. Set secure random values for `INGEST_API_KEY`, `TELEGRAM_WEBHOOK_SECRET`, `ADMIN_API_KEY`, `SIGNING_SECRET`.
5. Start app locally and expose HTTPS URL (e.g., tunnel) for webhook testing.
6. Register Telegram webhook:
   - `python scripts/register_telegram_webhook.py --bot-token "$TELEGRAM_BOT_TOKEN" --webhook-url "$APP_BASE_URL/telegram/webhook" --secret-token "$TELEGRAM_WEBHOOK_SECRET"`
7. Configure iPhone Shortcut `POST /ingest/ios-sms` with header `X-Ingest-Key: <INGEST_API_KEY>`.
8. Open `GET /auth/splitwise/start` and complete OAuth; callback stores encrypted token.
9. Sync groups:
   - `curl -X POST "$APP_BASE_URL/auth/splitwise/sync-groups" -H "X-Admin-Key: $ADMIN_API_KEY"`
10. Send sample SMS payload to verify Telegram prompt + actions.

## Production Safety Mode
Set `APP_ENV=production` only after all required secrets are configured.

Startup fails in production if:
- `INGEST_API_KEY` is missing
- `TELEGRAM_WEBHOOK_SECRET` is missing
- `SIGNING_SECRET` is default/weak

## iPhone Shortcut Build Spec

### Shortcut Type
Personal Automation triggered by `Message`.

### Filters
- sender is one of the bank/card shortcodes or contacts
- optional text contains any of: `Rs`, `debited`, `spent`, `UPI`, `purchase`, `card`

### Shortcut Steps
1. Receive message input.
2. Extract sender/contact if available.
3. Build dictionary payload.
4. Call `Get Contents of URL`.
   - method: `POST`
   - content type: JSON
   - URL: `$APP_BASE_URL/ingest/ios-sms`
   - header: `X-Ingest-Key: <INGEST_API_KEY>`
5. Optional local notification if HTTP request fails.

## Monitoring
Minimum:
- structured logs
- Telegram alerting for repeated failures (recommended)
- `/health` endpoint

## Admin Debug Endpoints
All require `X-Admin-Key`:
- `GET /admin/transactions/{id}`
- `GET /admin/drafts`
- `POST /admin/reparse/{transaction_id}`

## Backup
- daily DB snapshot
- optional export of transactions and drafts to JSON

## Acceptance Checks
- no duplicate Telegram prompts for same spend
- Telegram response latency under 10 seconds in normal operation
- draft never lost on backend restart
- simple equal split requires at most 3 taps after initial prompt
- webhook and ingest requests are rejected without valid shared secrets
