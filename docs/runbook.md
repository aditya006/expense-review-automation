# Runbook

## Environment Variables
- `APP_BASE_URL`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`
- `SPLITWISE_CLIENT_ID`
- `SPLITWISE_CLIENT_SECRET`
- `SPLITWISE_REDIRECT_URI`
- `DATABASE_URL`
- `SIGNING_SECRET`
- `LOG_LEVEL`

## Deployment Steps
1. Provision service.
2. Set environment variables.
3. Deploy backend.
4. Run DB migrations.
5. Register Telegram webhook.
6. Complete Splitwise auth.
7. Configure iPhone Shortcut endpoint.
8. Test with sample SMS.

## Persistence
- SQLite file on persistent volume.
- If host cannot guarantee persistence, use Postgres instead.
- Default decision: SQLite only if provider supports durable volume.

## Monitoring
Minimum:
- structured logs
- error alerts to Telegram or email
- `/health` endpoint

## Backup
- daily DB snapshot
- optional export of transactions and drafts to JSON

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
   - target: `/ingest/ios-sms`
5. Optional local notification if HTTP request fails.

### Multiple Shortcut Strategy
- Start with one generic banking automation.
- Split into multiple sender-family automations only if trigger noise is high.

### Failure UX
If backend is unavailable, show local iPhone notification:
- `Expense capture failed. Retry later.`

## Mobile Review Form Spec

### Purpose
Handle complex cases that do not fit Telegram quick actions.

### Fields
- amount
- merchant/description
- transaction date/time
- group selector
- participant multi-select
- split mode (`equal`, `custom`)
- custom amounts table
- notes
- actions: save draft, post to Splitwise, mark manually done, ignore

### UX Constraints
- mobile-first layout
- no login system for v1 if link is sufficiently secret and tied to Telegram flow
- URLs should expire or be unguessable

### Security Minimum
- signed review links with expiration
- HTTPS only
- CSRF protection if session-based forms are used

## Manual QA Scenarios
1. personal card spend
2. UPI shared dinner
3. grocery spend split with 2 friends
4. trip expense split with whole group
5. duplicate bank SMS
6. Splitwise auth expired
7. parser misses merchant
8. draft reopened and posted later
9. draft marked manually done
10. backend temporarily unavailable

## Acceptance Criteria
- no duplicate Telegram prompts for same spend
- Telegram response latency under 10 seconds in normal operation
- draft never lost on backend restart
- simple equal split requires at most 3 taps after initial prompt
