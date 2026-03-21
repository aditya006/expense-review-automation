# Expense Review Automation for Personal Splits

## Objective
Build a lightweight personal automation that captures spend alerts from iPhone SMS, asks the user to classify the spend in Telegram, and either:
- posts the expense to Splitwise automatically, or
- saves it as a draft for later manual handling.

## Primary User
- Single user
- Personal use only
- Comfortable with Telegram and simple mobile flows
- Uses iPhone
- Receives bank/card transaction SMS for UPI and credit card spends
- Uses Splitwise for shared expenses

## Core Problem
The user pays for shared expenses, forgets to add them to Splitwise, and loses track of whom to split with.

## Success Criteria
- Every relevant spend SMS generates a review prompt within 10 seconds.
- Simple cases take 1-2 taps to post to Splitwise.
- Complex cases can be saved as drafts and completed later.
- Duplicate SMS alerts do not create duplicate prompts.
- The system remains small, cheap, and maintainable by one developer.

## Non-Goals for V1
- OCR from receipts
- Generic iPhone app notification scraping
- WhatsApp integration
- Multi-user support
- Automated posting without user confirmation
- AI-based expense classification as a hard dependency

## User Journey

### Happy Path: Personal Spend
1. Bank SMS arrives on iPhone.
2. iPhone Shortcut triggers on sender/content match.
3. Shortcut sends raw SMS to backend.
4. Backend parses transaction.
5. Telegram bot sends message: `Spent Rs 850 at Zepto. What should I do?`
6. User taps `Me Only`.
7. Transaction is marked complete.
8. No Splitwise expense is created.

### Happy Path: Shared Group Expense
1. SMS arrives and is parsed.
2. Telegram bot asks for review.
3. User taps `Choose Group`.
4. Bot shows likely groups.
5. User selects `Goa Trip`.
6. Bot offers `Split All Equally`, `Choose People`, `Draft`.
7. User taps `Split All Equally`.
8. Backend creates Splitwise expense.
9. Bot confirms success with Splitwise link or summary.

### Complex Case: Needs Draft
1. SMS arrives and is parsed.
2. Bot prompts the user.
3. User taps `Draft`.
4. Backend stores the draft.
5. Later, user opens drafts via `/drafts`.
6. User edits participants or amounts in the review web form.
7. User confirms posting or marks it as manually handled.

### Parse Failure
1. SMS arrives but parser cannot confidently extract amount.
2. Backend stores as `parse_failed`.
3. Telegram sends: `I could not parse this transaction. Review manually?`
4. User opens manual review form.

## Functional Requirements

### Intake
- Accept raw SMS payloads from iPhone Shortcuts.
- Support multiple sender templates across banks and credit card issuers.
- Detect UPI/card transaction alerts only.
- Ignore OTPs, promotions, balance alerts, credit alerts, and repayment reminders.

### Parsing
- Extract amount, currency, merchant/payee, payment channel, last4, bank/card label, reference ID, timestamp.
- Persist original SMS for traceability.
- Assign parse confidence score.

### Review Flow
- Notify user via Telegram for every new parsed transaction.
- Allow actions: `Me Only`, `Choose Group`, `Draft`, `Ignore`.
- For group path, allow equal whole-group split, equal selected-people split, or custom split via form.
- Never post to Splitwise without explicit user action.

### Draft Management
- Save draft state for incomplete or complex transactions.
- Support reopening drafts from Telegram.
- Allow marking a draft as `posted`, `ignored`, or `manually handled`.

### Splitwise
- Authenticate once and reuse stored token.
- Fetch and cache groups and group members.
- Create expenses through API.
- Store Splitwise expense ID on success.
- Handle token expiration gracefully.

### Observability
- Log every intake, parse result, Telegram action, and Splitwise API result.
- Expose a small admin/debug view or queryable logs for troubleshooting.

## System Boundaries and Tradeoffs

### Why Not WhatsApp
- Official WhatsApp automation requires business platform setup.
- Template messages outside the service window are billable.
- Adds approval, opt-in, and account complexity not justified for personal use.

### Why Not Fully Local on iPhone
- Telegram callbacks, draft state, Splitwise tokens, and parsing rules are easier on a server.
- A backend is simpler overall than pushing logic into Shortcuts.

### Why Not Google Sheets as the Primary Backend
- Possible, but weaker for stateful flows and cleaner API composition.
- Better as an analytics export, not the source of truth.

## Defaults and Assumptions
- Currency is INR.
- User is the payer for all tracked transactions.
- The system is single-user only.
- Telegram is the only messaging channel in v1.
- iPhone SMS is the primary source of truth.
- SQLite is acceptable unless hosting lacks durable storage.
- Group/member cache can be refreshed daily or on demand.
- V1 optimizes for ease of maintenance over perfect automation accuracy.
