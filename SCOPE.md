# Product Scope

## Goal

Settle is a relational shared-expenses product for flatmates. An authenticated user can manage groups, maintain effective-dated memberships, create and edit expenses with every source split type, record repayments, import the supplied CSV without pre-cleaning, review uncertain rows, and trace every balance to its ledger entries.

## Implemented workflow

- Token login with an automatically seeded `demo / demo12345` account.
- Create and select groups.
- Add, date, update, and remove membership periods.
- Create, edit, list, and delete expenses using equal, unequal, percentage, or share splits.
- Store original currency amount, FX rate, and converted INR amount.
- Record and delete repayments separately from expenses.
- Import CSV (mandatory) and XLSX (additional), in replace or duplicate-safe append mode.
- Review and approve/reject uncertain imported rows.
- View all source rows in the import report and download CSV/JSON evidence.
- View net group balances, a per-person calculation trace, and greedy minimum-like settlement suggestions.

## Import contract

Required headers are `date`, `description`, `paid_by`, `amount`, `currency`, `split_type`, `split_with`, `split_details`, and `notes`. Parsing one bad row does not invalidate other rows. Every source row is assigned exactly one final ledger status:

`Posted + Needs review + Skipped = total CSV rows`

Each report row includes its CSV row number, detected problems, reasons, policies, chosen actions, review decision, and final status. The checked-in `backend/sample_data/expenses_export.csv` contains 42 source rows and is exercised by an automated import test.

## Anomaly catalogue

| Code | Detection rule | Policy | Expected action |
|---|---|---|---|
| `MISSING_DATE` | Date is blank | A financial row needs an effective date | Skip |
| `INVALID_DATE` | Date matches no supported parser | Do not invent a date | Skip |
| `AMBIGUOUS_DATE_FORMAT` | Slash-form date can be day-first or month-first | Preserve parsed proposal but surface ambiguity | Needs review |
| `AMBIGUOUS_OR_OUT_OF_SCOPE_DATE` | Date lies outside 2026-02-01 to 2026-05-31 | Do not guess a corrected year/date | Needs review |
| `INVALID_AMOUNT` | Amount is blank or non-numeric | Do not infer money | Skip |
| `ROUNDING_APPLIED` | More than two decimal places are supplied | Use decimal `ROUND_HALF_UP` to paise and disclose it | Post with info |
| `ZERO_AMOUNT` | Amount equals zero | Treat as a no-op | Skip |
| `NEGATIVE_AMOUNT_REFUND` | Negative value has refund/cancel language | Preserve as a negative expense and surface it | Post with warning |
| `NEGATIVE_AMOUNT_UNCLEAR` | Negative value lacks refund language | Do not infer its meaning | Needs review |
| `MISSING_CURRENCY` | Currency is blank | Use documented INR default only with disclosure | Needs review |
| `UNSUPPORTED_CURRENCY` | No configured INR exchange rate exists | Conversion cannot be guessed | Skip |
| `CURRENCY_CONVERTED` | Currency is not INR | Store original amount, rate, and converted INR | Post with info |
| `MISSING_PAYER` | `paid_by` is blank | The payer cannot be inferred | Skip |
| `NAME_NORMALIZED` | Alias/case/whitespace maps to a canonical person | Normalize deterministically and disclose | Post with info |
| `UNKNOWN_SPLIT_TYPE` | Split is not equal/unequal/percentage/share | Unsupported calculations are unsafe | Skip |
| `NO_SPLIT_PARTICIPANTS` | `split_with` yields no people | An expense cannot be allocated | Skip |
| `UNKNOWN_GUEST_MEMBER` | Dev/Kabir appears outside membership | Create a one-day auditable guest window | Needs review |
| `INACTIVE_MEMBER_IN_SPLIT` | Person is outside join/leave dates | Remove from proposed split, never charge silently | Needs review |
| `EQUAL_WITH_SPLIT_DETAILS` | Equal split also contains details | Structured `split_type` wins | Needs review |
| `MISSING_SPLIT_DETAILS` | Non-equal split has no values | Values cannot be inferred | Skip |
| `SPLIT_DETAILS_MISSING_PERSON` | A participant has no split value | Every participant needs a basis | Skip |
| `UNEQUAL_TOTAL_MISMATCH` | Unequal allocations do not equal expense | Never scale exact rupee allocations silently | Needs review |
| `PERCENT_TOTAL_NOT_100` | Percent values do not total 100 | Preserve proportions as a proposal | Needs review |
| `SETTLEMENT_DETECTED` | Payment/settlement language is detected | Keep repayments outside expense spending | Reclassify to settlement |
| `SETTLEMENT_RECIPIENT_UNCLEAR` | Payment has zero or multiple recipients | Never infer a recipient | Skip |
| `DEPOSIT_PAYMENT_DETECTED` | Deposit language is present | It may not be an ordinary shared expense | Needs review |
| `DUPLICATE_EXACT` | Same date, normalized description, payer, amount, people in file | Never double-post | Skip later row |
| `DUPLICATE_EXISTING_LEDGER` | Exact match already exists in ledger | Never double-post | Skip incoming row |
| `DUPLICATE_FUZZY_AMOUNT_MISMATCH` | Similar same-day description/people but payer or amount differs | A human chooses the winning row | Needs review |
| `DUPLICATE_EXISTING_FUZZY` | Incoming row resembles an existing ledger entry | A human chooses the winning row | Needs review |
| `DUPLICATE_EXISTING_SETTLEMENT` | Same repayment already exists | Never apply repayment twice | Skip incoming row |

## Relational database schema

| Table | Purpose and key relationships |
|---|---|
| `auth_user` | Authenticated owner; one-to-many with groups and import batches |
| `Person` | Canonical real-world person, referenced by memberships, splits, payers, and recipients |
| `ExpenseGroup` | User-owned ledger container |
| `GroupMembership` | Group + person + `starts_on`/`ends_on` effective interval + role |
| `ImportBatch` | Uploaded file, SHA-256 metadata, row counters, and report JSON for one group |
| `Expense` | Group expense with original amount/currency, FX rate, INR amount, payer, split type, import provenance, and status |
| `ExpenseSplit` | One expense/person allocation with INR amount and calculation basis; unique per pair |
| `Settlement` | Payment from one person to another, with currency conversion and import provenance |
| `ImportAnomaly` | Batch/row issue with code, reason, policy, action, review state, and optional expense/settlement link |

## Explicitly not completed locally

The codebase is production-container ready, but a public URL and public GitHub repository require the owner's hosting/GitHub account and are not fabricated in this document. Deployment configuration is in `docker-compose.prod.yml`, `backend/Dockerfile.prod`, and `frontend/Dockerfile.prod`.
