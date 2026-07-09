# Shared Expenses App Assignment

A Splitwise-style shared-expense application for importing messy flatmate expense data, detecting anomalies, tracking changing group membership over time, and explaining exactly how final balances are calculated.

This project keeps all documentation in one place. Earlier separate notes for scope, decisions, and AI usage have been merged into this unified `README.md`.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Tech Stack](#tech-stack)
- [Core Features Implemented](#core-features-implemented)
- [Product Scope](#product-scope)
- [Database Schema](#database-schema)
- [Import and Anomaly Handling](#import-and-anomaly-handling)
- [Balance Calculation](#balance-calculation)
- [API Overview](#api-overview)
- [Local Setup](#local-setup)
- [Docker Setup](#docker-setup)
- [Production-Style Docker Deployment](#production-style-docker-deployment)
- [Demo Flow](#demo-flow)
- [Engineering Decisions](#engineering-decisions)
- [AI Usage Disclosure](#ai-usage-disclosure)
- [Out of Scope for 2-Day MVP](#out-of-scope-for-2-day-mvp)

---

## Project Overview

The goal is to build a reliable shared-expense app for flatmates whose membership changes over time.

The app is designed around a messy import workflow rather than a clean manual-only entry flow. It can import shared expenses from CSV/XLSX, detect data issues, avoid silent assumptions, and explain what happened to every row.

The main product idea is:

> Do not silently change, delete, or guess risky financial data. Detect the issue, report it, and require review where needed.

---

## Tech Stack

- **Backend:** Django + Django REST Framework
- **Frontend:** React + Vite
- **Database:** SQLite for local development; PostgreSQL-ready Django ORM models
- **Authentication:** Django user login with DRF token authentication
- **Import:** CSV and XLSX support
- **Deployment:** Docker Compose, Gunicorn, Nginx, PostgreSQL-ready production setup

The assignment asks for `expenses_export.csv`. This implementation also accepts the uploaded `.xlsx` version without requiring manual editing.

---

## Core Features Implemented

- Login module using token authentication
- Groups, people, and date-bounded group memberships
- Expense creation and import
- Split types:
  - `equal`
  - `unequal`
  - `percentage`
  - `share`
- Settlement/payment recording
- Group-level net balances
- Minimal settlement suggestions showing who should pay whom
- Import report with:
  - anomaly code
  - severity
  - row number
  - policy
  - action taken
- Review gate for rows that require human approval before affecting balances
- CSV and XLSX import support
- Dockerized local and production-style setup

---

## Product Scope

The app handles flatmate/group expenses where people may join or leave during the time period of the imported data.

The import flow is treated as a first-class product feature, not as a one-time script. This matters because the provided data contains deliberate problems such as:

- duplicate rows
- fuzzy duplicates
- missing payer
- missing currency
- USD values
- negative refund rows
- inactive members in split lists
- settlement/payment rows mixed with expenses
- invalid percentage totals
- old/out-of-scope dates
- zero-value expenses
- guest members

The app should not crash on these rows and should not silently guess in a way that changes balances without review.

---

## Database Schema

### User

Django's built-in `auth.User` is used for login.

### Person

Represents a real flatmate or trip participant.

Fields:

- `id`
- `name`
- `canonical_name`
- `email`
- timestamps

### ExpenseGroup

Represents a group, house, or trip.

Fields:

- `id`
- `name`
- `created_by`
- timestamps

### GroupMembership

Represents membership over time.

Fields:

- `id`
- `group`
- `person`
- `starts_on`
- `ends_on`
- `role`

This is how the app knows that Meera should not be charged for April expenses and Sam should not be charged for March expenses.

### ImportBatch

Represents one uploaded file import attempt.

Fields:

- `id`
- `group`
- `uploaded_by`
- `source_filename`
- `status`
- `total_rows`
- `posted_rows`
- `review_rows`
- `skipped_rows`
- `report_json`
- timestamps

### Expense

Represents a ledger expense row.

Fields:

- `id`
- `group`
- `import_batch`
- `raw_row_number`
- `date`
- `description`
- `normalized_description`
- `paid_by`
- `amount_original`
- `currency`
- `fx_rate_to_inr`
- `amount_inr`
- `split_type`
- `split_with_raw`
- `split_details_raw`
- `notes`
- `status`

### ExpenseSplit

Represents the exact owed amount per person for an expense.

Fields:

- `id`
- `expense`
- `person`
- `amount_owed_inr`
- `basis`

### Settlement

Represents a payment/settlement between two people.

Fields:

- `id`
- `group`
- `import_batch`
- `raw_row_number`
- `date`
- `paid_by`
- `paid_to`
- `amount_original`
- `currency`
- `fx_rate_to_inr`
- `amount_inr`
- `notes`
- `status`

### ImportAnomaly

Represents a detected data problem or product decision point.

Fields:

- `id`
- `batch`
- `row_number`
- `code`
- `severity`
- `message`
- `policy`
- `action_taken`
- `requires_review`
- `status`
- `suggested_payload`

---

## Import and Anomaly Handling

The actual import file contains deliberate data problems. The importer detects and surfaces them instead of crashing or guessing silently.

Rows that require changes, deletion, or interpretation are not silently posted. They are stored with `REVIEW_REQUIRED` status and surfaced in the import report.

Posted balances only use rows whose status is `POSTED`.

| Code | Example from sheet | Detection | Policy | Action |
|---|---|---|---|---|
| `DUPLICATE_EXACT` | `Dinner at Marina Bites` and `dinner - marina bites` | Same date, payer, amount, people, very similar normalized description | Do not delete silently | Quarantine duplicate row; requires review |
| `DUPLICATE_FUZZY_AMOUNT_MISMATCH` | `Dinner at Thalassa` vs `Thalassa dinner` | Same date and people, similar description, different payer/amount | Human should decide winning row | Review required; not posted until approved |
| `CURRENCY_CONVERTED` | `Goa villa booking`, `Beach shack lunch`, `Parasailing` in USD | Currency is USD | Convert using configured import FX rate | Convert to INR and report rate |
| `NEGATIVE_AMOUNT_REFUND` | `Parasailing refund` `-30 USD` | Negative amount and refund-like description | Treat as refund, not an error | Import as negative expense/refund with report |
| `ZERO_AMOUNT` | `Dinner order Swiggy` amount `0` | Amount equals zero | No financial impact | Skip as no-op and report |
| `MISSING_PAYER` | `House cleaning supplies` | Empty `paid_by` | Cannot infer payer | Skip/review; not posted |
| `MISSING_CURRENCY` | `Groceries DMart` after trip | Empty currency | Do not crash; default domestic blank to INR but require review | Create review-required row with assumed INR |
| `NAME_NORMALIZED` | `priya`, `Priya S`, `rohan ` | Case, suffix, or whitespace variants | Canonicalize names | Map to Priya/Rohan and report |
| `SETTLEMENT_DETECTED` | `Rohan paid Aisha back` | Settlement words and one recipient | Do not treat as expense | Store as Settlement |
| `DEPOSIT_PAYMENT_DETECTED` | `Sam deposit share` | Deposit/payment-like description | Treat as payment, not shared expense | Store as Settlement/review |
| `INACTIVE_MEMBER_IN_SPLIT` | April groceries include Meera | Split member inactive on date | Do not charge inactive members silently | Review-required corrected split excluding inactive member |
| `MEMBER_NOT_ACTIVE_YET` | March expenses with Sam, if any | Date before membership start | Same as above | Review required |
| `UNKNOWN_GUEST_MEMBER` | `Dev's friend Kabir` | Person not in membership table | Guest can exist for trip/day, but must be visible | Create one-day guest membership; review required |
| `AMBIGUOUS_OR_OUT_OF_SCOPE_DATE` | Airport cab appears as old Excel date | Date outside expected Feb-May 2026 import window | Do not guess corrected date | Review required; not posted |
| `PERCENT_TOTAL_NOT_100` | Percent splits total 110% | Sum of percentages != 100 | Preserve ratios but require review | Normalize percentages to 100 only after review |
| `EQUAL_WITH_SPLIT_DETAILS` | Furniture row says equal but has share details | Equal split with details present | `split_type` wins | Ignore split details, report anomaly |
| `ROUNDING_APPLIED` | Cylinder amount `899.995` | More than paise precision | Round to paise using Decimal HALF_UP | Report if rounded |

---

## Balance Calculation

For each posted expense:

```text
paid_by.net += amount_inr
for every split:
    split_person.net -= amount_owed_inr
```

For each posted settlement/payment:

```text
payer.net += amount_inr
receiver.net -= amount_inr
```

A positive balance means the person should receive money.

A negative balance means the person should pay money.

### Money Precision

The app uses `Decimal` instead of floating-point math.

For split calculations:

- amounts are rounded to paise-level precision
- values are quantized to `0.01`
- final remainder is assigned to the last participant
- total split amount is guaranteed to equal the converted expense amount

---

## API Overview

- `POST /api/auth/token/` — login and get token
- `GET/POST /api/groups/` — groups
- `GET/POST /api/people/` — people
- `GET/POST /api/memberships/` — memberships with `starts_on` and `ends_on`
- `GET/POST /api/expenses/` — expenses
- `GET/POST /api/settlements/` — settlements/payments
- `POST /api/groups/{group_id}/import/` — import CSV/XLSX
- `GET /api/groups/{group_id}/balances/` — balances and suggested settlements
- `POST /api/anomalies/{id}/approve/` — approve an anomaly/row change
- `POST /api/anomalies/{id}/reject/` — reject an anomaly/row change

---

## Local Setup

### Backend

```bash
cd backend

# Python 3.12+ recommended
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# Git Bash / Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo
python manage.py test
python manage.py runserver
```

The backend runs at:

```text
http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at:

```text
http://localhost:5173
```

---

## Docker Setup

For the standard development Docker setup:

```bash
docker compose up --build
```

---

## Production-Style Docker Deployment

This repository includes a production-oriented Docker setup:

- `backend/Dockerfile.prod` runs Django through Gunicorn.
- `frontend/Dockerfile.prod` builds React and serves it through Nginx.
- `frontend/nginx.conf` serves the React app and reverse-proxies `/api`, `/admin`, and `/static` to Django.
- `docker-compose.prod.yml` runs PostgreSQL, backend, and frontend together.
- `.env.example` documents deployment environment variables.

### Run Production Stack Locally

```bash
cp .env.example .env
# Edit SECRET_KEY, POSTGRES_PASSWORD, ALLOWED_HOSTS, and trusted origins before real deployment.
docker compose -f docker-compose.prod.yml up --build
```

Open:

```text
http://localhost
```

Demo credentials are created when `SEED_DEMO=1`:

```text
username: demo
password: demo12345
```

### Useful Docker Commands

```bash
# Run migrations manually if needed
docker compose -f docker-compose.prod.yml exec backend python manage.py migrate

# Create an admin user
docker compose -f docker-compose.prod.yml exec backend python manage.py createsuperuser

# View backend logs
docker compose -f docker-compose.prod.yml logs -f backend

# Stop containers
docker compose -f docker-compose.prod.yml down

# Stop and remove database volume only when you want a clean database
docker compose -f docker-compose.prod.yml down -v
```

### Deployment Notes

For a real hosted deployment, set:

- `DEBUG=0`
- a strong `SECRET_KEY`
- a strong `POSTGRES_PASSWORD`
- `ALLOWED_HOSTS=your-domain.com`
- `CSRF_TRUSTED_ORIGINS=https://your-domain.com`
- `CORS_ALLOWED_ORIGINS=https://your-domain.com`
- `SEED_DEMO=0` after demo/testing is complete

The app still satisfies the assignment requirement of using relational databases only: local development can use SQLite, while the production Compose file uses PostgreSQL.

---

## Demo Flow

1. Start backend and frontend.
2. Login with a Django user.
3. Create or use the seeded group: `Flatmates Feb-Apr 2026`.
4. Upload `expenses_export.csv` or the provided `.xlsx` file from the Import page.
5. Read the import report.
6. Approve or reject review-required anomalies.
7. Open the Balances page to see group balances and settlement suggestions.

---

## Engineering Decisions

### 1. Framework Choice

Options considered:

- FastAPI + React
- Django + React
- Next.js full stack

Decision: **Django REST Framework + React**

Reason: The internship role explicitly values Django REST APIs, React components, relational schema design, and end-to-end ownership. Django also provides authentication, admin, ORM, migrations, and relational modeling quickly.

### 2. Database

Options considered:

- SQLite
- PostgreSQL
- MongoDB

Decision: **Django ORM with SQLite locally, PostgreSQL-ready**

Reason: The assignment requires relational databases only. SQLite is easy for local review, and the schema can move to PostgreSQL without changing app logic.

### 3. Membership Over Time

Options considered:

- Store one current member list per group
- Store membership windows with start/end dates

Decision: **Store date-bounded `GroupMembership` rows**

Reason: Sam joined mid-April and Meera moved out at the end of March. A current-only member list cannot answer historical balance questions correctly.

### 4. Import Anomalies

Options considered:

- Auto-fix everything silently
- Crash on bad rows
- Detect, report, and gate risky rows behind review

Decision: **Detect every anomaly, surface it, and choose a documented action**

Reason: The assignment explicitly says crashed imports and silent guesses are failing answers. Risky changed/deleted rows are marked as `REVIEW_REQUIRED`.

### 5. Duplicate Handling

Options considered:

- Keep both rows
- Delete the later row automatically
- Quarantine suspected duplicates

Decision: **Quarantine exact/fuzzy duplicates and require human approval**

Reason: Meera specifically asked to approve anything the app deletes or changes.

### 6. USD Handling

Options considered:

- Treat USD as INR
- Reject USD rows
- Convert using a configured import FX rate

Decision: **Convert USD to INR using a configured rate stored with every row**

Reason: Priya's request is that dollars cannot be treated like rupees. Storing the FX rate per row makes the calculation auditable.

### 7. Negative Amount Handling

Options considered:

- Reject all negative amounts
- Treat all negatives as refunds
- Use row context

Decision: **Negative amount with refund-like description is treated as a refund and reported**

Reason: `Parasailing refund` is clearly a cancelled slot refund. The importer still surfaces it because negative values affect balances.

### 8. Percent Split Total Not 100

Options considered:

- Reject row
- Normalize ratios
- Use literal percentages and create imbalance

Decision: **Normalize ratios only as a proposed calculation and require review**

Reason: This preserves intent without silently changing money owed.

### 9. Rounding

Options considered:

- Float math
- Decimal math rounded at the end
- Decimal math rounded per split with remainder assigned to the last participant

Decision: **Decimal math with paise-level rounding and final remainder adjustment**

Reason: This avoids floating-point drift and guarantees the sum of splits equals the converted expense amount.

### 10. AI Usage

Decision: **AI can generate scaffolding and point out edge cases, but the submitted code must be read and understood manually**

Reason: The live session may ask why individual lines exist.

---

## AI Usage Disclosure

### AI Tool Used

Primary AI collaborator: **ChatGPT GPT-5.5 Thinking**

### Key Prompts Used

1. "Read the assignment and explain the actual engineering task."
2. "Design a Django + React architecture for a shared expense app with messy import data."
3. "Generate a Django model schema for users, groups, memberships, expenses, splits, settlements, and anomalies."
4. "Write an importer that detects duplicate expenses, USD rows, missing payer/currency, inactive members, settlements, and inconsistent split details."
5. "Create documentation files: SCOPE.md, DECISIONS.md, README.md, and AI_USAGE.md."

### Cases Where AI Was Wrong and How It Was Corrected

#### 1. AI initially treated settlements as normal expenses

Problem: The row `Rohan paid Aisha back` was first modelled as a shared expense.

Why wrong: A repayment changes balances between two people but should not be split among the group.

Correction: Added `Settlement` as a separate model and added settlement detection logic.

#### 2. AI initially ignored membership dates

Problem: Early balance logic split every expense among everyone listed in `split_with`.

Why wrong: Sam joined mid-April and Meera moved out at the end of March. Historical membership matters.

Correction: Added `GroupMembership.starts_on` and `ends_on`, then made the importer flag inactive members in each split.

#### 3. AI initially used floating-point math

Problem: The first split calculation used Python `float`.

Why wrong: Money calculations using floats can create paise-level errors and make balances hard to explain.

Correction: Replaced floats with `Decimal`, quantized to `0.01`, and assigned remainder to the last participant.

#### 4. AI initially auto-deleted duplicates

Problem: Exact duplicates were silently ignored.

Why wrong: Meera requested approval for deletions/changes.

Correction: Duplicate rows are now stored as `REVIEW_REQUIRED` or skipped with an anomaly report. The user can approve or reject them.

#### 5. AI initially treated USD as INR

Problem: The first version did not convert USD.

Why wrong: Priya explicitly says the dollar values cannot be treated as rupees.

Correction: Added `fx_rate_to_inr` and `amount_inr`, and the import report records `CURRENCY_CONVERTED`.

---

## Out of Scope for 2-Day MVP

- Multi-currency historical FX API lookup
- Complex recurring expenses
- Bank reconciliation
- Real-time notifications
- Production SSO
- Full audit diff UI for every row edit

---

## Final Note

This project is intentionally built around correctness, reviewability, and explainability. The most important design decision is that financial rows with uncertain meaning are not silently posted into balances. They are detected, reported, and reviewed before affecting the ledger.
