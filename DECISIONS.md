# Engineering Decisions

Each entry records the decision, considered options, chosen approach, rationale, and trade-off.

## Import review model

- **Options:** silently normalize; reject the whole file; post valid rows and isolate uncertainty.
- **Chosen:** process rows independently and use `POSTED`, `REVIEW_REQUIRED`, or `SKIPPED`.
- **Reason:** flatmates can make progress while retaining control of financial ambiguity.
- **Trade-off:** review and report state add domain complexity.

## Duplicate handling

- **Options:** auto-delete; post all; quarantine every exact and fuzzy candidate for review.
- **Chosen:** create duplicate candidates as `REVIEW_REQUIRED`; a person explicitly approves posting or rejects/skips each row.
- **Reason:** no candidate changes balances while pending, and no source row is silently deleted or discarded.
- **Trade-off:** even obvious exact duplicates require a review click, preserving user control at the cost of more work.

## Re-import behavior

- **Options:** always append; always replace; selectable modes.
- **Chosen:** default replace of earlier imported ledger rows, with duplicate-safe append available.
- **Reason:** the supplied file is a full export and demo re-uploads must not multiply balances.
- **Trade-off:** replace removes prior review decisions for imported rows; manual rows are preserved.

## Negative amounts

- **Options:** reject all; convert to positive; infer refunds from context.
- **Chosen:** preserve negative values only when refund/cancellation language is explicit; otherwise review.
- **Reason:** sign is financially meaningful and must never be silently flipped.
- **Trade-off:** wording-based classification is conservative and may require extra review.

## Currency conversion

- **Options:** live market API; hard-coded converted value; per-import explicit rate.
- **Chosen:** user supplies the USD/INR rate; original amount, rate, and converted amount are stored.
- **Reason:** imports are reproducible and explainable without network volatility.
- **Trade-off:** the user is responsible for the chosen historical rate.

## Money precision and rounding

- **Options:** binary floats; database decimals with banker's rounding; decimals with half-up rounding.
- **Chosen:** `Decimal`, quantized to ₹0.01 using `ROUND_HALF_UP`; remainder goes to the last allocation.
- **Reason:** money stays exact and splits always add back to the expense total.
- **Trade-off:** the last participant can differ by one paise; the basis remains visible.

## Membership dates

- **Options:** current member list only; warn but charge inactive people; enforce effective intervals.
- **Chosen:** `starts_on <= expense date <= ends_on` (or no end date).
- **Reason:** Sam and Meera must not be charged outside their residency.
- **Trade-off:** historical entries require correct membership setup; specific trip guests get one-day auditable memberships.

## Split representation

- **Options:** store only raw formulas; calculate balances dynamically; persist normalized allocations.
- **Chosen:** store the raw import fields plus one `ExpenseSplit` row per person with INR amount and basis.
- **Reason:** every split type converges to an auditable ledger allocation and live calculation is simple.
- **Trade-off:** edited formulas must replace their persisted split rows transactionally.

## Settlements

- **Options:** negative expenses; ordinary expenses; separate relational model.
- **Chosen:** separate `Settlement` records.
- **Reason:** repayments reduce obligations but are not group consumption.
- **Trade-off:** balance calculations have two event sources, both shown in the trace.

## Settlement suggestions

- **Options:** preserve original debt edges; exhaustive minimum transaction search; greedy largest debtor/creditor matching.
- **Chosen:** greedy matching of largest balances.
- **Reason:** it yields a short, clear, deterministic set for a flatmate-sized group.
- **Trade-off:** it is not a formal globally minimal solver for every possible constraint set.

## Database and deployment

- **Options:** document store; SQLite only; Django ORM with SQLite locally and PostgreSQL in production.
- **Chosen:** relational Django models, SQLite development, PostgreSQL production Compose.
- **Reason:** relationships, constraints, transactions, and audit queries are core requirements.
- **Trade-off:** two database engines require testing production deployment separately.

## Frontend direction

- **Options:** retain the purple utility dashboard; copy the reference site; build a purpose-specific dark interface.
- **Chosen:** a distinct black/teal responsive product surface borrowing the reference's contrast, spacing, typography scale, borders, and teal actions.
- **Reason:** it matches the supplied visual intent while keeping the expense workflows legible.
- **Trade-off:** remote Google Fonts fall back to system fonts when offline.
