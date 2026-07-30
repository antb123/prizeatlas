## Goals

Look up OpenAlex Institution IDs for the position-1 flat affiliation on each `awards` row that already carries a curated `affiliate_ror`, and fill blank `awards.institution_openalex_id` cells only when the OpenAlex record's ROR echoes the requested ROR URL.

The lookup MUST abstain instead of guessing. A write SHALL occur only when OpenAlex returns a singleton institution record for the requested ROR, the record's `ror` field equals `https://ror.org/<ror_id>`, the existing ROR-side identity gates are clean, and the target `institution_openalex_id` cell is still blank when the write transaction begins. Success means the tool previews or applies an explicitly selected batch, emits claim-level source and outcome details for every selected `award_record_id`, never overwrites a curated value, and leaves the database healthy and the existing website build passing.

## Background

`datasets/awards.sqlite3` is the sole source of truth. Its `awards` table ends with four optional identifier fields; `institution_openalex_id` is `TEXT NOT NULL DEFAULT ''` and describes only the position-1 flat affiliation. All 3,096 cells are currently blank. Of 2,755 rows with a nonblank `affiliation_name`, 2,702 have a nonblank `affiliation_wikidata_qid`, and 2,503 of those now carry a curated `affiliate_ror` from the prior ROR pass (`datasets/docs/datasets-affiliation-ror-lookup-20260730.md`).

The OpenAlex `/institutions/{id}` endpoint accepts an OpenAlex ID or a `https://ror.org/<id>` URL in the path and returns a singleton institution object whose `id` is the OpenAlex URL form (`https://openalex.org/I...`), whose `ror` echoes the input URL, and whose `display_name` is the curated institution name. HTTP 404 means no match. The optional `api_key` query parameter raises the daily free-usage budget from $0.10/day to $1/day, which matters for list endpoints; singleton lookups fit the no-key budget for bounded runs. Official references: [OpenAlex Institutions](https://docs.openalex.org/api-entities/institutions), [OpenAlex Authentication & Pricing](https://developers.openalex.org/guides/authentication).

The ROR pass supplies every assumption, gate, report shape, and apply transaction this feature reuses: explicit row selectors, network research before a short transaction, claim-level JSON reports, blank-cell guards on writes, byte-for-byte value preservation, and the `datasets/scripts/lookup_ror.py:548-603` command-line contract. ROR never appears in the OpenAlex lookup key — the lookup key is the existing `affiliate_ror` value the ROR pass already curated, so the two passes form a deterministic chain (Wikidata QID → ROR → OpenAlex ID).

AGENTS.md names OpenAlex as a source for citation metrics and ORCID as a source for researcher identifiers; populating `institution_openalex_id` is the institution-side half of that source policy and uses the same external-ID discipline. The other three identifier fields (`orc_id`, `affiliate_ror`, `author_openalex_id`) are out of scope here.

## Assumptions

1. **Load-bearing:** `institution_openalex_id` stores a compact OpenAlex Institution ID such as `I136199984`, without the `https://openalex.org/` prefix.
2. **Load-bearing:** Only the position-1 `awards.institution_openalex_id` field is written; extra affiliations remain out of scope because `award_extra_affiliations` has no OpenAlex column and no ROR column.
3. **Load-bearing:** The lookup key is the row's current `affiliate_ror` value. The OpenAlex request path is `https://api.openalex.org/institutions/https://ror.org/<ror_id>` (URL-encoded), and the response `ror` field MUST equal `https://ror.org/<ror_id>` exactly. A 404 or any other mismatch abstains.
4. **Load-bearing:** The ROR identity gates — one QID under multiple distinct nonblank parent names, or one parent name with multiple distinct nonblank QIDs — still block OpenAlex enrichment across the same two affiliation stores (`awards` and `award_extra_affiliations`).
5. **Load-bearing:** `OPENALEX_API` is an optional environment variable sourced from `datasets/.env`. When unset the tool runs against the no-key daily budget; when set the tool passes it as the `api_key` query parameter for the larger daily budget. Missing, empty, or whitespace-only values are treated as unset. Bounded `--record-id` runs fit the no-key budget; `--all` SHOULD set `OPENALEX_API` to avoid the budget edge.
6. A row whose `affiliate_ror` is blank cannot be looked up and is reported as `blocked_missing_ror`; no name or Wikidata fallback is attempted.
7. A row whose `institution_openalex_id` is already nonblank is reported as `unchanged` and MUST NOT trigger a lookup or write.
8. The same compact ROR MAY appear on several award rows because one institution can host many laureates; one OpenAlex request serves all rows sharing that ROR.
9. OpenAlex returns at most one institution record for a ROR URL path. A response listing zero or many records, or one record whose `ror` field does not match the input, abstains.
10. The tool MUST pace uncached requests below one per 100 ms and MUST honor one valid `Retry-After` retry on HTTP 429; a repeated 429 fails visibly.
11. No branch, commit, push, merge, HTML display, extra-affiliation schema change, ROR lookup change, ORCID lookup, name matching, scoring, search-result order, or fallback authority is part of this work.

## Scope

Estimated implementation: about 340 lines across four files, plus blank-to-nonblank data updates whose count is determined by the reviewed lookup results.

| File | Current range | Required change |
|---|---:|---|
| `datasets/scripts/lookup_openalex.py` | New file | Add the read/lookup/report/apply command. |
| `datasets/tests/test_lookup_openalex.py` | New file | Add isolated API, selection, classification, and transaction tests. |
| `datasets/docs/datasets-affiliation-records-20260728.md` | `36-72`, `235-320` | Document the OpenAlex field, source order entry, ownership, command, abstentions, and post-write checks without rewriting unrelated historical counts. |
| `datasets/awards.sqlite3` | `awards.institution_openalex_id`, schema position 35 | Fill confirmed blank cells only; do not alter schema or any other field. |

No dependency, cache file, tracked candidate file, website module, template, archived CSV, normalizer mapping, validator check, or extra-affiliation table change is included.

Because the implementation touches more than three files, the companion TODO is `datasets/docs/datasets-affiliation-openalex-lookup-todo-20260730.md`.

## Command contract

`datasets/scripts/lookup_openalex.py` MUST be an ordinary standard-library Python command run from `datasets/` with `uv run`. It MUST require `--db awards.sqlite3` and exactly one operation:

- research for one or more repeatable `--record-id <award_record_id>` arguments;
- research for explicit `--all` in a curator-authorized whole-database backfill; or
- application of one reviewed `--apply <report.json>` artifact.

Research/preview mode MUST be the default for `--record-id` and `--all`, and its JSON stdout is the review artifact. Apply mode MUST be a separate `--apply <report.json>` operation that makes no OpenAlex request and applies only confirmed results from that exact reviewed artifact. `--all`, `--record-id`, and `--apply` MUST be mutually exclusive. Missing or duplicate requested IDs MUST fail before any OpenAlex request; duplicates are an input error rather than being silently collapsed.

The tool MUST select and report the requested records by exact `award_record_id`. In `--all` mode it MUST target only actionable backfill rows — those with nonblank `affiliate_ror` and blank `institution_openalex_id` — and report them by status. The blocking statuses (`blocked_missing_name`, `blocked_missing_qid`, `blocked_missing_ror`, `blocked_qid_name_conflict`, `blocked_name_qid_conflict`) and the `unchanged` status apply to both `--record-id` and `--all` runs whenever a row that meets the gate criteria happens to be in scope, so a full backfill still surfaces identity-conflict and pre-existing-value rows. A selected row whose `institution_openalex_id` is already nonblank MUST be reported as unchanged and MUST NOT trigger a lookup or write.

The command MUST write one JSON document to stdout and concise progress or failure messages to stderr. The report MUST include:

- database path, preview/apply mode, processed count, and per-status totals;
- for each selected `award_record_id`, the stored parent name, Wikidata QID, stored `affiliate_ror`, status, reason, and an `updates` object;
- for every API-backed result, the OpenAlex request URL (without the API key), the compact OpenAlex Institution ID, the institution display name, the echoed ROR URL, and the normalized response fields (`id`, `display_name`, `ror`);
- apply outcome and affected-row count when `--apply` is used.

The allowed row statuses are `confirmed`, `blocked_missing_name`, `blocked_missing_qid`, `blocked_missing_ror`, `blocked_qid_name_conflict`, `blocked_name_qid_conflict`, `abstained_not_found`, and `unchanged`. An unexpected OpenAlex response, transport failure, non-404 HTTP error, or malformed response shape is not an abstention; it MUST fail the command visibly.

### Requirement: Explicit selection — every run MUST have a bounded or explicit whole-database scope

#### Scenario: No selector

- WHEN the command receives `--db awards.sqlite3` without `--record-id`, `--all`, or `--apply`
- THEN argument validation fails before the database or network is touched

#### Scenario: Unknown selected record

- WHEN any requested `award_record_id` is absent
- THEN the command fails before the first OpenAlex request
- AND it does not process the remaining IDs

## OpenAlex resolution

The lookup key MUST be the exact `affiliate_ror` already curated on the row, validated against `^0[a-hj-km-np-tv-z0-9]{6}[0-9]{2}$`. The command MUST send one request per distinct eligible ROR, with the path `https://api.openalex.org/institutions/https://ror.org/<ror_id>` (URL-encoded), the `select=id,display_name,ror` query parameter, and an optional `api_key` query parameter when `OPENALEX_API_KEY` is set. It MUST set an identifying `User-Agent`, request JSON, use a finite timeout, pace network requests below OpenAlex's published limit, and reuse each response in memory for all selected rows with that ROR.

The response classifier MUST inspect the singleton object and reject any payload whose shape is not `{id: str, display_name: str, ror: str}` (HTTP 200 is a singleton, not a list). The classifier MUST fail visibly on a malformed object; it abstains only on HTTP 404 or on a well-formed object whose `ror` field does not equal `https://ror.org/<requested_ror>` exactly.

- HTTP 200 with a well-formed object whose `ror == "https://ror.org/<requested_ror>"` produces `confirmed`; the compact OpenAlex ID is extracted from `id` by stripping the `https://openalex.org/` prefix and re-validated against `^I[0-9]+$`.
- HTTP 404 produces `abstained_not_found`.
- HTTP 200 with a well-formed object whose `ror` differs from the requested URL produces `abstained_not_found` (the response is recorded in the report for review).
- HTTP 200 with a missing `ror`, non-string required field, malformed `id`, or `id` whose suffix is not `I<digits>` after the prefix is stripped MUST fail the command visibly.

Name or location differences between the dataset and the OpenAlex record MUST be preserved in the report for review, but they MUST NOT silently rewrite `affiliation_name`, city, country, ROR, QID, or any other field. The tool MUST NOT follow parent/child/predecessor/successor relationships or any other OpenAlex relation as a replacement identity.

Before network work, the command MUST view `awards` position 1 and every `award_extra_affiliations` position as one affiliation relation. If one QID appears under more than one distinct nonblank parent name, every selected row using that QID receives `blocked_qid_name_conflict`. If one selected parent name carries more than one distinct nonblank QID, every selected row using that name receives `blocked_name_qid_conflict`. Both checks use the entire live relation, not only the selected subset, so a bounded run cannot hide a conflict outside its scope. Missing QIDs do not create an inverse conflict; they remain `blocked_missing_qid` on their own selected rows.

### Requirement: Exact ROR echo — only one OpenAlex record echoing the requested ROR MUST be proposed

#### Scenario: Unique exact match

- WHEN OpenAlex returns one institution whose `ror` field equals `https://ror.org/<requested_ror>`
- THEN every eligible selected row with that ROR is `confirmed`
- AND its `updates` object contains only the compact `institution_openalex_id`
- AND one network request serves all of those rows

#### Scenario: Not found

- WHEN OpenAlex returns HTTP 404 for the requested ROR
- THEN the row is `abstained_not_found`
- AND `updates` is empty

#### Scenario: Wrong ROR echo

- WHEN OpenAlex returns a 200 response whose `ror` field differs from `https://ror.org/<requested_ror>`
- THEN the row is `abstained_not_found`
- AND the response is recorded in the report for review

#### Scenario: Conflicting stored parent names

- WHEN the same QID appears under two distinct nonblank parent names anywhere across the two affiliation stores
- THEN all selected rows using that QID are `blocked_qid_name_conflict`
- AND no OpenAlex request is made for those rows

#### Scenario: Conflicting stored QIDs

- WHEN one parent name carries two distinct nonblank QIDs anywhere across the two affiliation stores
- THEN all selected position-1 rows using that parent name are `blocked_name_qid_conflict`
- AND no OpenAlex request is made for those rows

#### Scenario: Missing ROR

- WHEN a selected row has a blank or malformed `affiliate_ror`
- THEN it is `blocked_missing_ror`
- AND the tool does not fall back to Wikidata or name matching

## Database application

Research mode MUST finish every OpenAlex request and serialize the complete result set without opening a write transaction. Apply mode MUST load the reviewed report, validate its version and complete structure, reject unexpected statuses or update fields, and make no network request. The report is untrusted input: its values may become only parameterized database values, never paths, commands, SQL identifiers, identity-policy overrides, or log payloads. The validated `updates` object on a `confirmed` result MUST equal exactly `{"institution_openalex_id": <compact_id>}` where `<compact_id>` is the suffix of the response `id` after `https://openalex.org/`; any other shape, extra keys, or different compact ID MUST fail validation.

The operator MUST make the repository-required timestamped database backup before invoking `--apply`; the command MUST print that prerequisite in its apply-mode start message but does not create or manage backups.

One short transaction MUST apply confirmed results by exact `award_record_id`. Each update MUST require all of the following current values to equal the researched snapshot:

- `award_record_id`;
- `affiliation_name`;
- `COALESCE(affiliation_wikidata_qid, '')` (the column is nullable);
- `affiliate_ror`;
- blank `institution_openalex_id`.

Each confirmed row MUST affect exactly one row. A zero-row or multi-row result indicates concurrent drift or a broken invariant; the command MUST roll back the whole batch and report failure. Nonconfirmed and unchanged results never enter the transaction. The command MUST not offer an overwrite option.

### Requirement: Blank-only guarded writes — apply mode MUST preserve every curated value

#### Scenario: Successful reviewed batch

- WHEN `--apply <report.json>` receives the reviewed preview and all confirmed rows still have their researched ROR and blank OpenAlex cell
- THEN one transaction fills only `institution_openalex_id`
- AND the JSON apply result reports the exact number of affected rows
- AND apply mode makes no OpenAlex request

#### Scenario: Row changes after lookup

- WHEN a confirmed row's ROR or OpenAlex cell changes before its guarded update
- THEN the transaction rolls back
- AND no row from that batch remains changed
- AND the command exits nonzero with a factual drift error

## Failure behavior and observability

In research mode, HTTP 429 MUST honor a valid `Retry-After` once; a repeated 429 fails. Other HTTP errors, URL errors, timeouts, invalid JSON, and invalid response shapes MUST fail visibly. In apply mode, a missing, unreadable, or structurally invalid report MUST fail before a transaction opens. The tool MUST NOT convert infrastructure failure into `abstained_not_found`.

Logs MUST identify the operation, safe ROR or `award_record_id`, outcome, and next action without logging the API key, the response body beyond the structured fields already in the report, or the full URL with credentials. ROR IDs, OpenAlex IDs, and Wikidata QIDs are public identifiers; no credentials or personal payloads are introduced.

OpenAlex response scores, search-result order, related institution lists, and type-ahead suggestions MUST NOT be used. The command MUST NOT call the OpenAlex `/works`, `/authors`, or `/sources` endpoints, the OpenAlex advanced-query endpoint, Wikidata, or a model fallback. These paths add ambiguity without improving the exact-ROR-echo contract.

## Compatibility

The schema, row count, existing values, website behavior, and generated CSV headers remain unchanged. Successful enrichment changes only blank `institution_openalex_id` cells. The website already reads and exports the field verbatim through `datasets/website/build.py:141-176,192-228,800-885,2501-2509`.

Rows that cannot be resolved safely remain blank. The report is the claim-level research handoff required by `AGENTS.md`; it MUST be retained with the run handoff because no dedicated provenance columns exist.

## Verification

Implementation verification MUST proceed in this order:

1. Record a before snapshot of row count, distinct `award_record_id` count, nonblank `institution_openalex_id` count, and every pre-existing nonblank `institution_openalex_id` value.
2. Run focused tests covering selector validation, both cross-store identity-conflict directions, blank/malformed ROR abstention, exact-match classification, wrong-ror abstention, 404 abstention, malformed-response failure, compact-ID validation, request deduplication, network failure, report validation, blank-only updates, no-network apply, and full rollback on drift.
3. Run a preview against representative live rows, including one unique active ROR, one missing ROR, one pre-existing OpenAlex ID, and one ROR in the live `umbrella-qid` backlog; redirect and inspect the complete JSON review artifact.
4. Back up `awards.sqlite3` with the timestamped `.openalex.bak` convention.
5. Apply the exact reviewed report artifact. For the research run that created it, pass every assigned `award_record_id` explicitly; use `--all` only when the curator explicitly authorizes the full backfill.
6. Confirm that the row count and distinct `award_record_id` count did not change, all pre-existing nonblank OpenAlex values are byte-for-byte unchanged, and the number of newly nonblank cells equals the report's affected-row count.
7. Run `sqlite3 awards.sqlite3 "PRAGMA integrity_check;"` and require exactly `ok`.
8. Run `uv run scripts/validate_awards.py`, save the full before/after group output, and verify that no affiliation identity group was added or enlarged.
9. Run `uv run scripts/normalize_affiliations.py` in dry-run mode and inspect its report; do not apply unrelated normalization.
10. Run `uv run pytest tests/test_lookup_openalex.py`, `uv run pytest tests/`, and `uv run ruff check`.
11. Run `uv run website/build.py --base-url https://example.org/awards/` as the final live-data gate.

The implementation SHALL follow the project instruction not to create a Git branch. Unit tests are part of implementation; no commit, push, merge, or deployment is requested.