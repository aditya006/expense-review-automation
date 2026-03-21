# Architecture

## Chosen Stack
- Backend: Python + FastAPI
- Database: SQLite for v1
- Messaging: Telegram Bot API
- SMS Trigger: iPhone Shortcuts personal automation
- Hosting: personal computer or easy cloud deploy with simple steps

## Why This Stack
- FastAPI is quick to build and easy to maintain.
- SQLite is enough for single-user state and drafts.
- Telegram is simpler than WhatsApp for personal bots.
- A tiny backend centralizes auth, state, parsing, and callbacks.

## Components
1. iPhone Shortcut Automations
2. FastAPI backend
3. SQLite database
4. Telegram bot webhook handler
5. Splitwise API client
6. Optional mobile web review UI

## High-Level Flow
1. SMS received on iPhone.
2. Shortcut posts payload to backend.
3. Backend parses and deduplicates.
4. Backend saves transaction.
5. Backend sends Telegram review prompt.
6. User responds in Telegram.
7. Backend updates transaction state.
8. If needed, backend calls Splitwise API.
9. Backend confirms result in Telegram.

## Data Model (V1)

### `transactions`
- `id` UUID primary key
- `source` text (`ios_sms`)
- `status` text (`captured`, `needs_review`, `draft`, `posted`, `ignored`, `parse_failed`, `error`)
- `raw_message` text
- `sender` text
- `contact_name` text nullable
- `received_at` datetime
- `occurred_at` datetime nullable
- `amount_minor` integer nullable
- `currency` text default `INR`
- `merchant` text nullable
- `channel` text nullable (`upi`, `card`, `bank`, `unknown`)
- `account_label` text nullable
- `last4` text nullable
- `reference_id` text nullable
- `parse_confidence` real nullable
- `dedupe_key` text
- `suggested_group_id` text nullable
- `suggested_group_name` text nullable
- `suggested_participants_json` text nullable
- `notes` text nullable
- `telegram_message_id` text nullable
- `splitwise_expense_id` text nullable
- `posted_at` datetime nullable
- `created_at` datetime
- `updated_at` datetime

### `draft_actions`
- `id` UUID primary key
- `transaction_id` UUID foreign key
- `draft_payload_json` text
- `draft_status` text (`open`, `manually_done`, `posted`, `discarded`)
- `created_at` datetime
- `updated_at` datetime

### `group_cache`
- `group_id` text primary key
- `group_name` text
- `members_json` text
- `updated_at` datetime

### `merchant_rules`
- `id` UUID
- `merchant_pattern` text
- `default_group_id` text nullable
- `default_participants_json` text nullable
- `split_mode` text nullable
- `confidence` real
- `created_at` datetime
- `updated_at` datetime

### `event_log`
- `id` UUID
- `transaction_id` UUID nullable
- `event_type` text
- `payload_json` text
- `created_at` datetime

## Repository Structure Recommendation
```text
expense-bot/
  app/
    main.py
    config.py
    db.py
    models.py
    schemas.py
    routers/
      ingest.py
      telegram.py
      review.py
      auth.py
    services/
      parser_service.py
      telegram_service.py
      splitwise_service.py
      transaction_service.py
      dedupe_service.py
    parsers/
      generic.py
      hdfc.py
      icici.py
      sbi_card.py
    templates/
      review_form.html
    static/
  tests/
    test_parsers.py
    test_ingest.py
    test_telegram.py
    test_splitwise.py
  scripts/
    register_telegram_webhook.py
    seed_groups.py
  docs/
    product-spec.md
    architecture.md
    api-spec.md
    parser-guide.md
    runbook.md
```

## Build Order
1. Phase 1: Skeleton (FastAPI app, SQLite models, health endpoint, basic config)
2. Phase 2: Ingest + Parsing (ingest endpoint, normalization, generic parser, dedupe, persistence)
3. Phase 3: Telegram (bot setup, webhook handler, review prompt, `Me Only`/`Draft`/`Ignore` actions)
4. Phase 4: Splitwise (OAuth, group/member sync, create expense for simple equal splits)
5. Phase 5: Review Form (manual edit form, participant selection, custom amounts)
6. Phase 6: Hardening (error handling, event logging, retries, tests, deployment)

## Risks and Mitigations
- iPhone message automation inconsistencies by sender format. Mitigation: validate with real device/senders and split automations if needed.
- SMS format variance across banks. Mitigation: incremental parser modules, persist raw SMS, manual override path.
- Splitwise auth expiry/failure. Mitigation: preserve drafts, never drop context, add re-auth instructions in admin view.
- Telegram callback complexity growth. Mitigation: keep Telegram flow shallow, push complex edits to web form.
