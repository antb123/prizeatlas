# Affiliation ROR lookup implementation TODO

Specification: `datasets/docs/specs/datasets-affiliation-ror-lookup-20260730.md`

Implement only the exact-QID ROR crosswalk for position-1 `awards.affiliate_ror`. Do not add name matching, HTML output, extra-affiliation ROR storage, OpenAlex lookup, schema changes, QID cleanup, or normalizer changes. The project instruction forbids creating a Git branch.

## ROR-1 — Add the lookup and guarded-apply command

**ID:** ROR-1
**Depends-on:** none
**Files:** `datasets/scripts/lookup_ror.py` (new file)

**Relevant assumptions:**

1. `affiliate_ror` stores a compact nine-character ROR ID without the URL prefix.
2. Only the position-1 `awards.affiliate_ror` field is written; extra affiliations remain out of scope.
3. Only an exact Wikidata external-ID crosswalk is automatically writable.
4. QID→multiple-name and name→multiple-QID conflicts are blocked across both affiliation stores.
5. Exact active and inactive ROR records are writable; withdrawn records and successor relationships are not.
6. A missing or malformed Wikidata QID remains blank.
7. One ROR ID may legitimately repeat on several award rows.
8. Pace uncached API calls below 2,000 requests per five minutes and honor one valid `Retry-After`.
9. Do not create a branch or expand the feature into display, normalization, OpenAlex, or QID correction.

**Steps → verify:**

1. Add an `argparse` command requiring `--db` and exactly one of repeatable `--record-id`, `--all`, or `--apply <report.json>` → invoke every valid and invalid combination and verify invalid combinations exit before database/network work.
2. Read requested rows by exact `award_record_id`; reject duplicate and unknown requested IDs before network work → verify the error names the offending IDs and no partial result is emitted.
3. Build a read-only union of position 1 from `awards` and positions 2+ from `award_extra_affiliations`; detect both identity-conflict directions across the complete live relation → verify conflicted selected rows receive the specified blocked status and produce no request.
4. Query the ROR v2 `query` endpoint once per distinct eligible QID using a quoted QID and all statuses, with a finite timeout, identifying user agent, pacing, one `Retry-After` retry, and in-memory response reuse → verify duplicate-QID rows share one request.
5. Fail on transport, HTTP, JSON, malformed, or incomplete-page responses; do not turn infrastructure failure into a no-match abstention → verify stderr is concise and stdout does not contain a misleading successful report.
6. Match only records whose `external_ids` contain the exact requested Wikidata QID; classify zero, one, or several exact matches and active, inactive, or withdrawn status exactly as specified → verify scores and result order have no effect.
7. Extract only `https://ror.org/<id>` values matching `^0[a-hj-km-np-tv-z0-9]{6}[0-9]{2}$` → verify malformed URLs and excluded Crockford letters fail.
8. Emit a versioned JSON research report with the required run summary, per-record snapshot, source, ROR metadata, reason, status, and single-field `updates` object → inspect that it contains no URL query string or response body.
9. Make `--apply` load and strictly validate the reviewed report without network access → verify unexpected statuses, update keys, shapes, or identifier formats fail before a transaction opens.
10. Apply confirmed rows in one transaction with parameterized values and guards on exact `award_record_id`, researched parent name, researched QID, and blank `affiliate_ror`; require one affected row per update and provide no overwrite option → verify any drift rolls back the entire batch.

## ROR-2 — Prove lookup, selection, and transaction behavior

**ID:** ROR-2
**Depends-on:** ROR-1
**Files:** `datasets/tests/test_lookup_ror.py` (new file)

**Relevant assumptions:**

1. Compact ROR IDs have the specified nine-character form.
3. Exact Wikidata external-ID membership is the only writable match.
4. Identity conflicts are checked in both directions across both stores.
5. Active and inactive exact records are writable; withdrawn records are blocked.
6. Missing or malformed Wikidata QIDs remain blank.
7. Repeated ROR IDs across award rows are valid.

**Steps → verify:**

1. Create temporary SQLite fixtures containing the four fields needed for guarded writes plus an `award_extra_affiliations` table → keep every test isolated from `datasets/awards.sqlite3`.
2. Test no selector, mutually exclusive operations, duplicate record IDs, and an unknown record ID → map directly to “No selector” and “Unknown selected record.”
3. Mock ROR responses for one exact active record, one exact inactive record, one withdrawn record, no exact record among false positives, several exact records, invalid ROR URLs, invalid identifier characters, malformed JSON shapes, and truncated results → map directly to “Unique exact crosswalk” and “Search false positive,” and prove every failure/abstention contract.
4. Test a QID under multiple names and one name under multiple QIDs with conflicts placed in position 2 as well as position 1 → map directly to “Conflicting stored parent names” and “Conflicting stored QIDs.”
5. Test blank and malformed QIDs and a selected row with a pre-existing ROR ID → map directly to “Missing QID” and prove no request or overwrite occurs.
6. Select multiple rows sharing one eligible QID → prove one ROR request produces per-record confirmed results.
7. Save a valid preview report, apply it, and assert only blank `affiliate_ror` changes → map directly to “Successful reviewed batch” and prove apply makes no network call.
8. Change the name, QID, and ROR cell separately between report creation and apply; include a batch where drift occurs after an earlier update → map directly to “Row changes after lookup” and prove full rollback every time.
9. Run `cd datasets && uv run pytest tests/test_lookup_ror.py` → require all focused tests to pass.

## ROR-3 — Document ROR ownership and operating procedure

**ID:** ROR-3
**Depends-on:** ROR-1
**Files:** `datasets/docs/datasets-affiliation-records-20260728.md:36-72,235-320`

**Relevant assumptions:**

1. The stored value is the compact ROR identifier.
2. The field describes only position 1.
3. Name matching is insufficient.
4. Both identity-conflict directions block enrichment.
5. Inactive is valid when exact; withdrawn and successor substitution are not.
6. Rows without QIDs remain blank.

**Steps → verify:**

1. Add ROR after Wikidata in the affiliation source order and add `affiliate_ror` to the position-1 field reference → verify the text does not imply ROR replaces Wikidata or belongs to a sub-name.
2. Add the lookup command to the ownership table and describe preview-report-review-backup-apply as the only scripted ROR write path → verify bounded tasks still require exact repeated `award_record_id` selectors.
3. Document exact-QID matching, both cross-store conflict gates, active/inactive/withdrawn handling, compact storage, report retention, blank-only guards, and no name fallback → compare every rule with the reviewed specification.
4. Add the focused ROR test and nonblank-value preservation checks to post-write validation without rewriting unrelated stale snapshot counts → inspect the diff to confirm surrounding user-owned affiliation documentation was preserved.

## ROR-4 — Research and apply confirmed ROR identifiers

**ID:** ROR-4
**Depends-on:** ROR-1, ROR-2, ROR-3
**Files:** `datasets/awards.sqlite3` (`awards.affiliate_ror`, schema position 33)

**Relevant assumptions:**

1. Store only the compact ROR ID.
2. Update position 1 only.
3. Apply only exact Wikidata crosswalks.
4. Leave both kinds of unresolved identity conflict blank.
5. Accept exact active or inactive records; block withdrawn records.
6. Leave missing-QID rows blank.
7. Repeated institution IDs are expected.
8. Use the published API limit.
9. Do not alter schema, display, names, QIDs, or extra affiliations.

**Steps → verify:**

1. Save before-state queries for total rows, distinct `award_record_id` values, nonblank ROR count, all pre-existing nonblank ROR values, and full `validate_awards.py --detail 10000` output → retain these with the research handoff.
2. Run the focused test file, then create a bounded preview report using one repeated `--record-id` per assigned row; use `--all` only with explicit curator authorization → inspect every `confirmed`, blocked, abstained, and unchanged result before continuing.
3. Retain the reviewed JSON report as claim-level provenance and create `awards.sqlite3.$(date +%Y%m%d-%H%M%S).ror.bak` → verify the backup exists and opens before applying.
4. Apply that exact report with `--apply`; do not rerun live lookups during application → require the command's affected count to equal the number of confirmed report entries.
5. Re-run the before-state queries → require unchanged row counts and IDs, byte-for-byte preservation of pre-existing ROR values, and exactly the reported number of new nonblank cells.
6. Run `sqlite3 awards.sqlite3 "PRAGMA integrity_check;"` → require exactly `ok`.
7. Run `uv run scripts/validate_awards.py` and diff the full group lists → require no identity group to be added or enlarged.
8. Run `uv run scripts/normalize_affiliations.py` without `--apply` → inspect the dry-run report and make no unrelated normalization change.
9. Run `uv run pytest tests/` and `uv run ruff check` → require both to pass, or report the exact pre-existing failure without changing unrelated code.
10. Run `uv run website/build.py --base-url https://example.org/awards/` → require a successful final build against the enriched live database.
