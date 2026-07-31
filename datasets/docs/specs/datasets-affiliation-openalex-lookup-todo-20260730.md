# Affiliation OpenAlex lookup implementation TODO

Specification: `datasets/docs/specs/datasets-affiliation-openalex-lookup-20260730.md`

Implement the exact-ROR-echo lookup only. Do not add name matching, schema changes, website output, extra-affiliation
storage, ORCID, author lookup, ROR changes, or normalization.

## OPENALEX-1 — Add preview and guarded apply

**ID:** OPENALEX-1
**Depends-on:** none
**Files:** `datasets/scripts/lookup_openalex.py` (new)

**Assumptions:**

1. Store compact `I<digits>` IDs in position 1 only.
2. Exact ROR echo is the only writable match.
3. Read optional `OPENALEX_API` from `datasets/.env`.
4. `--all` means nonblank ROR plus blank OpenAlex ID.

**Steps → verify:**

1. Require `--db` and exactly one of repeatable `--record-id`, `--all`, or `--apply` → invalid and duplicate selectors fail before database or network access.
2. Read exact rows and both affiliation stores; apply both QID/name conflict gates → blocked rows make no request.
3. Read `OPENALEX_API` from `datasets/.env` and never emit it → missing and blank values behave as no key.
4. Query once per distinct eligible ROR with the three-field `select`, identifying user agent, finite timeout, 100 ms pacing, and one valid `Retry-After` retry → shared RORs share one request.
5. Confirm only a valid `I<digits>` ID with exact ROR echo; treat 404 and wrong echo as not found; fail on malformed or infrastructure responses → each result matches the spec table.
6. Emit the versioned report with the five-field row snapshot, sanitized `request_url`, and `openalex_record` object or `null` → strict validation ties confirmed updates to the record ID and exact ROR echo.
7. Apply confirmed rows in one guarded transaction with no network access or overwrite path → any row drift rolls back the complete batch.

## OPENALEX-2 — Test the command

**ID:** OPENALEX-2
**Depends-on:** OPENALEX-1
**Files:** `datasets/tests/test_lookup_openalex.py` (new)

**Assumptions:**

1. Exact ROR echo is the only successful classification.
2. HTTP 404 has `openalex_record: null`.
3. Identity conflicts use both affiliation stores.

**Steps → verify:**

1. Use temporary SQLite fixtures only → the live database never changes.
2. Test missing, conflicting, duplicate, and unknown selectors → no premature network access.
3. Test exact echo, wrong echo, 404, malformed object/ID/JSON, other HTTP errors, transport failure, one retry, repeated 429, and invalid `Retry-After` → failure and abstention contracts hold.
4. Test both cross-store identity-conflict directions, missing ROR, unchanged rows, and repeated ROR request reuse → status and request counts match.
5. Test `.env` missing, blank, and populated without exposing the key → request and report are safe.
6. Test valid apply plus name, QID, ROR, and target-cell drift → writes are blank-only and drift fully rolls back.
7. Run `cd datasets && uv run pytest tests/test_lookup_openalex.py` → all focused tests pass.

## OPENALEX-3 — Document ownership and operation

**ID:** OPENALEX-3
**Depends-on:** OPENALEX-1
**Files:** `datasets/docs/datasets-affiliation-records-20260728.md:36-72,238-316`

**Assumptions:**

1. OpenAlex follows the curated ROR and never replaces it.
2. The compact ID describes position 1 only.

**Steps → verify:**

1. Add OpenAlex after ROR in the source order, field reference, and ownership table → its authority and position are unambiguous.
2. Document preview → review → backup → apply, exact ROR echo, `.env`, conflict gates, report retention, and blank-only writes → instructions match the command.
3. Add focused tests and pre-existing-value comparison to the validation list → unrelated counts and prose remain unchanged.

## OPENALEX-4 — Research and apply data

**ID:** OPENALEX-4
**Depends-on:** OPENALEX-1, OPENALEX-2, OPENALEX-3
**Files:** `datasets/awards.sqlite3` (`awards.institution_openalex_id`, position 35)

**Assumptions:**

1. Only confirmed blank cells may change.
2. This task needs curator-supplied record IDs or explicit `--all` authorization.

**Steps → verify:**

1. Stop unless the curator supplies exact record IDs or explicitly authorizes `--all`.
2. Save row counts, existing OpenAlex values, and full validator output → retain the before state.
3. Run and inspect one preview for that exact scope → retain the JSON report.
4. Create and open a timestamped `.openalex.bak` → backup exists before writing.
5. Apply the exact report → affected rows equal confirmed results.
6. Re-run the before-state queries, integrity check, validator diff, normalizer dry-run, tests, Ruff, and website build → no unrelated data or behavior changed.
