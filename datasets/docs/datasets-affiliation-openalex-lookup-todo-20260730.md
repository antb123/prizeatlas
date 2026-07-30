# Affiliation OpenAlex lookup implementation TODO

Specification: `datasets/docs/datasets-affiliation-openalex-lookup-20260730.md`

Implement only the exact-ROR-echo OpenAlex crosswalk for position-1 `awards.institution_openalex_id`. Do not add name matching, HTML output, extra-affiliation OpenAlex storage, ORCID lookup, schema changes, QID cleanup, ROR-script changes, or normalizer changes. The project instruction forbids creating a Git branch.

## OPENALEX-1 — Add the lookup and guarded-apply command

**ID:** OPENALEX-1
**Depends-on:** none
**Files:** `datasets/scripts/lookup_openalex.py` (new file)

**Relevant assumptions:**

1. `institution_openalex_id` stores a compact OpenAlex Institution ID such as `I136199984`, without the `https://openalex.org/` prefix.
2. Only the position-1 `awards.institution_openalex_id` field is written; extra affiliations remain out of scope.
3. The lookup key is the row's existing `affiliate_ror`; the response `ror` field MUST equal `https://ror.org/<ror_id>` exactly. 404 or wrong-ror abstains; malformed shape fails.
4. QID→multiple-name and name→multiple-QID conflicts are blocked across both affiliation stores, just as in the ROR pass.
5. `OPENALEX_API` is an optional env var sourced from `datasets/.env`; absent/empty values are unset.
6. Rows without a valid nonblank `affiliate_ror` are `blocked_missing_ror`; no name or Wikidata fallback.
7. One ROR may legitimately repeat on several award rows; one request serves all.
8. Pace uncached requests below one per 100 ms and honor one valid `Retry-After`.
9. Do not create a branch or expand the feature into display, normalization, ORCID, ROR-script changes, or QID correction.

**Steps → verify:**

1. Add an `argparse` command requiring `--db` and exactly one of repeatable `--record-id`, `--all`, or `--apply <report.json>` → invoke every valid and invalid combination and verify invalid combinations exit before database/network work.
2. Read requested rows by exact `award_record_id`; reject duplicate and unknown requested IDs before network work → verify the error names the offending IDs and no partial result is emitted.
3. Build a read-only union of position 1 from `awards` and positions 2+ from `award_extra_affiliations`; detect both identity-conflict directions across the complete live relation → verify conflicted selected rows receive the specified blocked status and produce no request.
4. Load `OPENALEX_API` from `os.environ` once; pass it as the `api_key` query parameter only when nonblank → verify the request URL logged to stderr omits the key and that an unset/empty value is functionally equivalent to no key.
5. Query the OpenAlex `/institutions/https://ror.org/<ror_id>` endpoint once per distinct eligible ROR with `select=id,display_name,ror`, a finite timeout, identifying user agent, pacing, one `Retry-After` retry, and in-memory response reuse → verify duplicate-ROR rows share one request.
6. Classify HTTP 200 (well-formed shape, ror matches) as `confirmed`, HTTP 404 as `abstained_not_found`, HTTP 200 with well-formed shape but mismatching `ror` as `abstained_not_found`, and any other HTTP status, transport failure, or malformed shape as a visible failure → verify stderr is concise and stdout does not contain a misleading successful report.
7. Extract the compact OpenAlex ID from the response `id` field by stripping `https://openalex.org/` and re-validate against `^I[0-9]+$` → verify malformed `id` values fail the command.
8. Emit a versioned JSON research report with the required run summary, per-record snapshot, source URL, normalized response fields, reason, status, and single-field `updates` object → inspect that it contains no `api_key` value and no extra update keys.
9. Make `--apply` load and strictly validate the reviewed report without network access → verify unexpected statuses, update keys/shapes, malformed response fields, missing ror-echo, or unverified compact-ID extraction fail before a transaction opens.
10. Apply confirmed rows in one transaction with parameterized values and guards on exact `award_record_id`, researched parent name, `COALESCE(affiliation_wikidata_qid, '')`, researched `affiliate_ror`, and blank `institution_openalex_id`; require one affected row per update and provide no overwrite option → verify any drift rolls back the entire batch.

## OPENALEX-2 — Prove lookup, selection, and transaction behavior

**ID:** OPENALEX-2
**Depends-on:** OPENALEX-1
**Files:** `datasets/tests/test_lookup_openalex.py` (new file)

**Relevant assumptions:**

1. Compact OpenAlex Institution IDs match `^I[0-9]+$`.
3. Exact ROR echo (`response.ror == "https://ror.org/<requested_ror>"`) is the only writable match.
4. Identity conflicts are checked in both directions across both stores.
6. Missing or malformed `affiliate_ror` rows remain `blocked_missing_ror`.
7. Repeated RORs across award rows share one request.
8. Malformed response shapes fail visibly, not as abstentions.

**Steps → verify:**

1. Create temporary SQLite fixtures containing the four identifier fields plus an `award_extra_affiliations` table → keep every test isolated from `datasets/awards.sqlite3`.
2. Test no selector, mutually exclusive operations, duplicate record IDs, and an unknown record ID → map directly to "No selector" and "Unknown selected record."
3. Mock OpenAlex responses for one exact match (ror echoes), one wrong-ror match (well-formed but `ror` differs), HTTP 404, malformed JSON shape (missing fields), non-string `ror`, malformed `id` (not `https://openalex.org/I<digits>`), HTTP 429 with `Retry-After`, HTTP 500, transport errors, and invalid JSON → map directly to "Unique exact match", "Wrong ROR echo", and "Not found"; prove every failure/abstention contract.
4. Test a QID under multiple names and one name under multiple QIDs with conflicts placed in position 2 as well as position 1 → map directly to "Conflicting stored parent names" and "Conflicting stored QIDs."
5. Test blank and malformed `affiliate_ror` and a selected row with a pre-existing `institution_openalex_id` → map directly to "Missing ROR" and prove no request or overwrite occurs.
6. Select multiple rows sharing one eligible ROR → prove one OpenAlex request produces per-record confirmed results.
7. Save a valid preview report, apply it, and assert only blank `institution_openalex_id` changes → map directly to "Successful reviewed batch" and prove apply makes no network call.
8. Change the ROR, name, and OpenAlex cell separately between report creation and apply; include a batch where drift occurs after an earlier update → map directly to "Row changes after lookup" and prove full rollback every time.
9. Verify `OPENALEX_API` unset/empty values behave identically and that the request URL recorded in the report never contains the API key.
10. Run `cd datasets && uv run pytest tests/test_lookup_openalex.py` → require all focused tests to pass.

## OPENALEX-3 — Document OpenAlex ownership and operating procedure

**ID:** OPENALEX-3
**Depends-on:** OPENALEX-1
**Files:** `datasets/docs/datasets-affiliation-records-20260728.md:36-72,235-320`

**Relevant assumptions:**

1. The stored value is the compact OpenAlex Institution ID.
2. The field describes only position 1.
3. ROR echo is the only writable signal; name matching is insufficient.
4. Both identity-conflict directions block enrichment.
5. Missing or malformed `affiliate_ror` rows remain blank.
6. The lookup key is the existing ROR, not the Wikidata QID.

**Steps → verify:**

1. Add OpenAlex after ROR in the affiliation source order and add `institution_openalex_id` to the position-1 field reference → verify the text does not imply OpenAlex replaces ROR/Wikidata or belongs to a sub-name.
2. Add the lookup command to the ownership table and describe preview-report-review-backup-apply as the only scripted OpenAlex write path → verify bounded tasks still require exact repeated `award_record_id` selectors.
3. Document exact-ROR echo, both cross-store conflict gates, HTTP 200/404/malformed handling, compact storage, `OPENALEX_API` env var from `datasets/.env`, report retention, blank-only guards, and no name fallback → compare every rule with the reviewed specification.
4. Add the focused OpenAlex test and nonblank-value preservation checks to post-write validation without rewriting unrelated stale snapshot counts → inspect the diff to confirm surrounding user-owned affiliation documentation was preserved.

## OPENALEX-4 — Research and apply confirmed OpenAlex identifiers

**ID:** OPENALEX-4
**Depends-on:** OPENALEX-1, OPENALEX-2, OPENALEX-3
**Files:** `datasets/awards.sqlite3` (`awards.institution_openalex_id`, schema position 35)

**Relevant assumptions:**

1. Store only the compact OpenAlex Institution ID.
2. Update position 1 only.
3. Apply only exact ROR echoes.
4. Leave both kinds of unresolved identity conflict blank.
5. Leave missing-ROR rows blank.
6. Repeated institution IDs are expected.
7. Use the documented OpenAlex auth/budget model.
8. Do not alter schema, display, names, ROR, QIDs, or extra affiliations.

**Steps → verify:**

1. Save before-state queries for total rows, distinct `award_record_id` values, nonblank OpenAlex count, all pre-existing nonblank OpenAlex values, and full `validate_awards.py --detail 10000` output → retain these with the research handoff.
2. Run the focused test file, then create a bounded preview report using one repeated `--record-id` per assigned row; use `--all` only with explicit curator authorization → inspect every `confirmed`, blocked, abstained, and unchanged result before continuing.
3. Retain the reviewed JSON report as claim-level provenance and create `awards.sqlite3.$(date +%Y%m%d-%H%M%S).openalex.bak` → verify the backup exists and opens before applying.
4. Apply that exact report with `--apply`; do not rerun live lookups during application → require the command's affected count to equal the number of confirmed report entries.
5. Re-run the before-state queries → require unchanged row counts and IDs, byte-for-byte preservation of pre-existing OpenAlex values, and exactly the reported number of new nonblank cells.
6. Run `sqlite3 awards.sqlite3 "PRAGMA integrity_check;"` → require exactly `ok`.
7. Run `uv run scripts/validate_awards.py` and diff the full group lists → require no identity group to be added or enlarged.
8. Run `uv run scripts/normalize_affiliations.py` without `--apply` → inspect the dry-run report and make no unrelated normalization change.
9. Run `uv run pytest tests/` and `uv run ruff check` → require both to pass, or report the exact pre-existing failure without changing unrelated code.
10. Run `uv run website/build.py --base-url https://example.org/awards/` → require a successful final build against the enriched live database.