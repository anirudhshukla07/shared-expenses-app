# AI Usage Disclosure

## Tools used

- OpenAI Codex for requirement auditing, implementation, test design, documentation, and UI iteration.
- Local shell/Docker for deterministic Django tests and Vite production builds.
- No AI-generated financial records or hidden anomaly decisions are used at runtime.

## Important prompts

- Build a complete shared-expenses product, not merely a Dockerized importer.
- Audit the existing code requirement by requirement before implementing gaps.
- Accept the original CSV unchanged, detect at least 12 deliberate problems, and never crash the entire import for one malformed row.
- Provide dated membership, every source split type, explainable balance breakdowns, settlements, review decisions, and a downloadable row-level report.
- Make the frontend visually similar to the supplied black, white, and teal ecommerce reference.

## Where AI output was wrong and how it was corrected

### 1. Tests reported success with zero discovered tests

- **Detection:** test output was inspected rather than trusting the exit code; Django reported no executed cases.
- **Correction:** tests were moved into a discoverable `expenses/tests/` package and the command now names the app. The current suite reports eight executed tests.

### 2. Review counts used anomalies instead of source rows

- **Detection:** one CSV row can generate multiple anomaly records, making dashboard totals exceed the file row count.
- **Correction:** batch counters and pending counts are derived from unique ledger row numbers. The invariant is asserted in the importer and an original-CSV integration test.

### 3. Docker used an unreliable Node/npm setup

- **Detection:** frontend container/build behavior was compared with a direct production Vite build.
- **Correction:** Node dependencies are installed from the frontend lockfile and the final bundle is built in the production Dockerfile, then served by Nginx.

### 4. Early work optimized row counts instead of the full product

- **Detection:** the assignment was mapped against the UI and showed no usable membership editor, expense editor, settlement form, or calculation trace.
- **Correction:** the app now exposes the complete workflow across Overview, Members, Expenses, and Import Review.

### 5. A suggested Render path did not match this repository

- **Detection:** the referenced Dockerfile path was checked against the actual two-service directory structure.
- **Correction:** deployment instructions use the checked-in production Compose and the real `backend/Dockerfile.prod` / `frontend/Dockerfile.prod` paths. No public URL is claimed without a real deployment.

### 6. The first CSV fixture conversion serialized dates as datetimes

- **Detection:** the original-CSV integration test saw only three anomaly classes; inspecting the generated CSV revealed values such as `2026-02-01T00:00:00`, which the documented CSV date parser rejected.
- **Correction:** spreadsheet datetime cells are exported as ISO dates (`YYYY-MM-DD`). The 42-row import test then passed and detected at least 12 distinct anomaly codes.

### 7. The first report-download query used DRF's reserved `format` parameter

- **Detection:** the API test returned HTTP 404 even though the action route existed.
- **Correction:** the endpoint uses `?export=csv|json`, avoiding REST Framework renderer negotiation.

## Human-review boundary

AI assisted with code and prose, but runtime financial ambiguity remains controlled by explicit policies and user approval. Duplicate candidates, unclear dates, membership conflicts, negative values, and questionable transformations remain visible in the import report.
