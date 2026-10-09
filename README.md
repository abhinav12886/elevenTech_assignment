# Django Wallet-Based Per-Minute Session Billing

Backend for prepaid 1:1 consultation sessions: wallet recharge, a strict session state machine, and idempotent per-minute billing.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

SQLite is the default database. To use PostgreSQL, set `DATABASE_URL`, for example:

```bash
export DATABASE_URL=postgres://user:password@localhost:5432/wallet_billing
python manage.py migrate
```

## Tests

```bash
python manage.py test
```

## Auth and roles

- `POST /api/auth/register/` with `{ "email", "password", "role": "USER"|"PROVIDER" }`
- `POST /api/auth/token/` with `{ "email", "password" }` (JWT)
- Send `Authorization: Bearer <access>`

## API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/wallet/` | Current balance |
| POST | `/api/wallet/recharge/` | `{amount}` → pending `reference` |
| POST | `/api/wallet/recharge/callback/` | Mock webhook `{reference, status}` |
| POST | `/api/sessions/` | Optional `{per_minute_cost}` (default 50) |
| POST | `/api/sessions/{id}/assign/` | `{provider_id}` |
| POST | `/api/sessions/{id}/accept/` | Provider |
| POST | `/api/sessions/{id}/start/` | User; requires balance ≥ 5 × rate |
| POST | `/api/sessions/{id}/bill/` | Charge due minutes; auto-ends if next minute cannot be paid |
| POST | `/api/sessions/{id}/end/` | User or provider |
| POST | `/api/sessions/{id}/cancel/` | Before the session starts |
| GET | `/api/sessions/{id}/` | |

## Session state machine

```mermaid
stateDiagram-v2
  [*] --> unassigned: create
  unassigned --> assigned: assign
  assigned --> accepted_by_provider: provider_accepts
  accepted_by_provider --> in_progress: user_starts
  in_progress --> completed: user_or_provider_or_system_ends
  unassigned --> cancelled: cancel
  assigned --> cancelled: cancel
  accepted_by_provider --> cancelled: cancel
```

Invalid transitions return HTTP 400.

## ER diagram

```mermaid
erDiagram
  User ||--|| Wallet : has
  User ||--o{ RechargeTransaction : initiates
  User ||--o{ Session : books
  User ||--o{ Session : provides
  Session ||--o{ BillingTick : billed_as
```

- **Wallet**: one per user, `balance >= 0`
- **RechargeTransaction**: unique `reference`, statuses `pending|success|failed`
- **Session**: lifecycle, frozen `per_minute_cost`, billed totals, `ended_by` / `end_reason`
- **BillingTick**: unique `(session, minute_index)` so a minute is never charged twice

## Implementation decisions

- **Decimal money** only; a check constraint plus debit guards keep the wallet non-negative.
- **JWT + USER/PROVIDER roles** as allowed by the BRD.
- **Charge the current open minute** at billing time (`floor(elapsed/60) + 1`). Minute 0 is due as soon as the session is in progress, so three minutes of talk time bill 3 × rate.
- **Idempotent recharge**: a success callback credits only on the first `pending → success` transition. Repeats return 200 and do not credit again.
- **Idempotent billing**: unique billing ticks plus `select_for_update` on session and wallet.
- **Start gate**: balance must cover 5 × the session's per-minute cost; a user may have only one `in_progress` session.
- **Insufficient balance mid-session**: skip the unpaid minute, keep the remaining balance, mark `ended_by=system` and `end_reason=Insufficient Balance`, persist billable seconds.
- **No Celery**; billing is a synchronous API as specified. SQLite is used locally; Postgres is optional via `DATABASE_URL`.
