# API Spec

## Endpoint: `POST /ingest/ios-sms`
Purpose:
- intake endpoint called by iPhone Shortcut
- authenticated via `X-Ingest-Key` (or bearer token fallback)

Request body:
```json
{
  "sender": "HDFCBK",
  "contact_name": "HDFC Bank",
  "message": "Rs.850 spent on HDFC Bank Card xx1234 at ZEPTO on 20-03-2026...",
  "received_at": "2026-03-20T14:05:21+05:30",
  "device_name": "Aditya iPhone"
}
```

Response:
```json
{
  "ok": true,
  "transaction_id": "uuid",
  "status": "needs_review"
}
```

Behavior:
- validate payload
- compute dedupe key
- reject duplicate if already seen
- parse SMS
- store transaction
- queue Telegram notification

Required header in secure mode:
- `X-Ingest-Key: <INGEST_API_KEY>`

## Endpoint: `POST /telegram/webhook`
Purpose:
- receive Telegram messages and inline button callbacks
- verify Telegram webhook secret header (`X-Telegram-Bot-Api-Secret-Token`)

Handles:
- `/start`
- `/drafts`
- `/pending`
- callback button presses
- deep links for specific transaction actions

## Endpoint: `GET /review/{transaction_id}`
Purpose:
- render mobile review form for complex edits
- requires signed token query parameter `?t=<signed_token>`

Displays:
- parsed merchant
- parsed amount
- group selection
- participant selection
- split mode
- editable description
- notes
- draft/post actions

## Endpoint: `POST /review/{transaction_id}`
Purpose:
- save manual review changes or post to Splitwise
- requires signed token query parameter `?t=<signed_token>` or admin key override

Request body:
```json
{
  "group_id": "12345",
  "participant_ids": ["u1", "u2", "u3"],
  "split_mode": "equal",
  "description": "Zepto groceries",
  "notes": "Shared dinner supplies",
  "action": "post"
}
```

## Endpoint: `GET /auth/splitwise/start`
Purpose:
- begin Splitwise OAuth flow

## Endpoint: `GET /auth/splitwise/callback`
Purpose:
- receive Splitwise OAuth callback and save token securely

## Optional Debug Endpoints
- `GET /health`
- `GET /transactions/{id}`
- `GET /drafts`
- `POST /admin/reparse/{transaction_id}`

## Telegram UX Spec

### Primary Notification Template
Message:
- `Spent Rs 850 at Zepto via card ending 1234. What should I do?`

Buttons:
- `Me Only`
- `Choose Group`
- `Draft`
- `Ignore`

### After Group Selection
Message:
- `Use this expense for Goa Trip?`

Buttons:
- `Split All Equally`
- `Choose People`
- `Open Form`
- `Draft`

### Draft Confirmation
Message:
- `Saved as draft. You can finish it later from /drafts.`

### Success Confirmation
Message:
- `Posted to Splitwise: Rs 850 in Goa Trip split among 4 people.`

### Failure Confirmation
Message:
- `I could not post this to Splitwise. The transaction is still saved as a draft.`

### Commands
- `/start`
- `/pending`
- `/drafts`
- `/help`

### Telegram State Model
Store callback payloads referencing transaction ID, action type, current step, and optional selected group ID.
Avoid putting full state in callback data. Use short references and look up transaction context in DB.

## Splitwise Integration Spec

### Supported V1 Operations
- authorize app
- fetch current user
- fetch groups
- fetch friends/group members
- create expense

### Create Expense Behavior
Required input:
- description
- amount
- group ID or participants
- split distribution
- paid by current user
- owed by selected users

### Default V1 Policies
- equal split: split across selected participants including payer unless user indicates otherwise
- group-wide equal split: all active group members in selected group participate
- personal spend: no Splitwise expense
- draft: persist prepared payload and skip API call

### Error Handling
If Splitwise call fails:
- preserve draft
- log API response
- notify user in Telegram
- offer retry

### Token Handling
- store encrypted at rest if possible
- minimum: store in secrets-backed environment or local encrypted blob
- refresh/re-auth flow should be manual and explicit
