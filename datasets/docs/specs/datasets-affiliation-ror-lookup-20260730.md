## Goals

Provide a safe, repeatable way to look up Research Organization Registry (ROR) identifiers for the position-1 flat affiliation on each award row and fill blank `awards.affiliate_ror` cells when the ROR organization can be tied to the row's already-verified Wikidata identity.

The lookup MUST abstain instead of guessing. A write SHALL occur only when one non-withdrawn ROR record contains the row's exact `affiliation_wikidata_qid`, neither the QID nor the stored parent name has an unresolved identity conflict across either affiliation store, and the target `affiliate_ror` cell remains blank when the write transaction begins.

Success means the tool can preview or apply an explicitly selected batch, emits claim-level source and outcome details for every selected `award_record_id`, never overwrites a curated value, and leaves the database healthy and the existing website build passing.

## Background

`datasets/awards.sqlite3` is the sole source of truth. Its `awards` table now ends with four optional identifier fields; `affiliate_ror` is `TEXT NOT NULL DEFAULT ''` and describes only the position-1 flat affiliation. All 3,096 cells are currently blank. Of 2,755 rows with a nonblank `affiliation_name`, 2,702 have a nonblank `affiliation_wikidata_qid`, representing 579 distinct QIDs, while 53 named rows still lack a QID.

The existing affiliation policy makes Wikidata identity authoritative for the ranked parent stored in `affiliation_name` (`datasets/docs/datasets-affiliation-records-20260728.md:36-56,60-72`). It forbids copying an identifier by name and requires writes by exact `award_record_id` with blank-cell guards (`datasets/docs/datasets-affiliation-records-20260728.md:235-274,276-308`). Nine current QIDs occur under more than one stored parent name, as reported by `uv run scripts/validate_awards.py --check umbrella-qid`; those groups require identity cleanup before ROR enrichment.

ROR's official guidance recommends its query parameter when a structured external identifier such as a Wikidata QID is available. The API v2 query endpoint searches `external_ids`, whose supported types include Wikidata, and returns active records by default. This plan deliberately requests all statuses so an inactive or withdrawn exact match is reported rather than mistaken for no match. Official references: [matching organization names](https://ror.readme.io/docs/matching), [query parameter](https://ror.readme.io/docs/api-query), [ROR data structure](https://ror.readme.io/docs/ror-data-structure), and [API limits](https://ror.readme.io/docs/rest-api).

No existing script looks up or writes `affiliate_ror`. `datasets/scripts/enrich.py:420-486,492-641` establishes the closest repository pattern: explicit row selectors, network research before a short transaction, JSON results, and guarded database updates. `datasets/scripts/lookup_coordinates.py:28-48,141-170,198-223` establishes visible network failures and a small standard-library command-line tool. Tests for lookup scripts import functions directly and mock network calls (`datasets/tests/test_lookup_coordinates.py:39-94`).

## Assumptions

1. **Load-bearing:** `affiliate_ror` stores the compact nine-character identifier such as `03vek6s52`, without the `https://ror.org/` prefix.
2. **Load-bearing:** This feature covers only `awards.affiliate_ror`, which belongs to the position-1 flat affiliation; extra affiliations remain out of scope because `award_extra_affiliations` has no ROR column.
3. **Load-bearing:** An exact Wikidata external-ID crosswalk is the only automatically writable match; name, acronym, score, result order, and ROR's affiliation matcher are not sufficient.
4. **Load-bearing:** A QID used by more than one distinct nonblank parent name, or a parent name carrying more than one distinct nonblank QID, is blocked until the identity conflict is curated; both checks span `awards` and `award_extra_affiliations`.
5. An exact active or inactive ROR record is writable because an inactive record can correctly identify an organization that has ceased operating; a withdrawn record and all successor relationships are review information only and MUST NOT be substituted automatically.
6. Rows without a valid nonblank `affiliation_wikidata_qid` remain blank and are reported as blocked rather than searched by name.
7. The same confirmed ROR ID MAY appear on several award rows because the same institution can have several laureates and awards.
8. The ROR API's current maximum of 2,000 requests per five minutes is sufficient for at most 579 distinct-QID lookups, but the client still paces uncached requests and honors `Retry-After`.
9. No branch, commit, push, merge, HTML display, extra-affiliation schema change, OpenAlex lookup, institution-name normalization, or QID correction is part of this work.

## Scope

Estimated implementation: about 320 lines across four files, plus blank-to-nonblank data updates whose count is determined by the reviewed lookup results.

| File | Current range | Required change |
|---|---:|---|
| `datasets/scripts/lookup_ror.py` | New file | Add the read/lookup/report/apply command. |
| `datasets/tests/test_lookup_ror.py` | New file | Add isolated API, selection, classification, and transaction tests. |
| `datasets/docs/datasets-affiliation-records-20260728.md` | `36-72`, `235-320` | Document the ROR field, source order, ownership, command, abstentions, and post-write checks without rewriting unrelated historical counts. |
| `datasets/awards.sqlite3` | `awards.affiliate_ror`, schema position 33 | Fill confirmed blank cells only; do not alter schema or any other field. |

No dependency, cache file, tracked candidate file, website module, template, archived CSV, normalizer mapping, validator check, or extra-affiliation table change is included.

Because the implementation touches more than three files, the companion TODO is `datasets/docs/specs/datasets-affiliation-ror-lookup-todo-20260730.md`.

## Command contract

`datasets/scripts/lookup_ror.py` MUST be an ordinary standard-library Python command run from `datasets/` with `uv run`. It MUST require `--db awards.sqlite3` and exactly one operation:

- research for one or more repeatable `--record-id <award_record_id>` arguments;
- research for explicit `--all` in a curator-authorized whole-database backfill; or
- application of one reviewed `--apply <report.json>` artifact.

Research/preview mode MUST be the default for `--record-id` and `--all`, and its JSON stdout is the review artifact. Apply mode MUST be a separate `--apply <report.json>` operation that makes no ROR request and applies only confirmed results from that exact reviewed artifact. `--all`, `--record-id`, and `--apply` MUST be mutually exclusive. Missing or duplicate requested IDs MUST fail before any ROR request; duplicates are an input error rather than being silently collapsed.

The tool MUST select and report the requested records by exact `award_record_id`. In `--all` mode it SHOULD target rows with a nonblank `affiliation_name` and blank `affiliate_ror`; it still reports rows blocked by a missing or conflicting QID. A selected row whose `affiliate_ror` is already nonblank MUST be reported as unchanged and MUST NOT trigger a lookup or write.

The command MUST write one JSON document to stdout and concise progress or failure messages to stderr. The report MUST include:

- database path, preview/apply mode, processed count, and per-status totals;
- for each selected `award_record_id`, the stored parent name, Wikidata QID, status, reason, and an `updates` object;
- for every API-backed result, the ROR source URL, compact ROR ID, ROR display name, record status, and exact Wikidata external IDs returned by ROR;
- apply outcome and affected-row count when `--apply` is used.

The allowed row statuses are `confirmed`, `blocked_missing_name`, `blocked_missing_qid`, `blocked_qid_name_conflict`, `blocked_name_qid_conflict`, `blocked_withdrawn`, `abstained_not_found`, `abstained_ambiguous`, and `unchanged`. An unexpected ROR response or transport failure is not an abstention; it MUST fail the command visibly.

### Requirement: Explicit selection — every run MUST have a bounded or explicit whole-database scope

#### Scenario: No selector

- WHEN the command receives `--db awards.sqlite3` without `--record-id`, `--all`, or `--apply`
- THEN argument validation fails before the database or network is touched

#### Scenario: Unknown selected record

- WHEN any requested `award_record_id` is absent
- THEN the command fails before the first ROR request
- AND it does not process the remaining IDs

## ROR resolution

The lookup key MUST be the exact uppercase `affiliation_wikidata_qid`. The command MUST send one API v2 query per distinct eligible QID, quoting the identifier and requesting all statuses. It MUST set an identifying `User-Agent`, request JSON, use a finite timeout, pace network requests below ROR's published limit, and reuse each response in memory for all selected rows with that QID.

The response classifier MUST inspect the returned records rather than trust search result count or order. A record matches only when one of its `external_ids` entries has type `wikidata` and its `all` values contain the exact requested QID. The response MUST be complete: when `number_of_results` is not equal to the number of returned `items`, the command fails rather than classify a truncated first page.

- Exactly one exact active or inactive record produces `confirmed`; the ROR status remains explicit in the report.
- No exact record produces `abstained_not_found`.
- More than one exact record produces `abstained_ambiguous`.
- One exact withdrawn record produces `blocked_withdrawn` and no update.

The compact value MUST be extracted only from an exact `https://ror.org/<id>` record ID and validated against `^0[a-hj-km-np-tv-z0-9]{6}[0-9]{2}$` before it enters `updates`. A malformed ID or response shape MUST fail the command.

Name or location differences between the dataset and an exact-QID ROR record MUST be preserved in the report for review, but they MUST NOT silently rewrite `affiliation_name`, city, country, QID, or any other field. The tool MUST NOT follow a parent, child, predecessor, or successor relationship as a replacement identity.

Before network work, the command MUST view `awards` position 1 and every `award_extra_affiliations` position as one affiliation relation. If one QID appears under more than one distinct nonblank parent name, every selected row using that QID receives `blocked_qid_name_conflict`. If one selected parent name carries more than one distinct nonblank QID, every selected row using that name receives `blocked_name_qid_conflict`. Both checks use the entire live relation, not only the selected subset, so a bounded run cannot hide a conflict outside its scope. Missing QIDs do not create an inverse conflict; they remain `blocked_missing_qid` on their own selected rows.

### Requirement: Exact external-ID match — only one non-withdrawn record containing the row QID MUST be proposed

#### Scenario: Unique exact crosswalk

- WHEN ROR returns one active or inactive record whose Wikidata external IDs contain the requested QID
- THEN every eligible selected row with that QID is `confirmed`
- AND its `updates` object contains only the compact `affiliate_ror`
- AND one network request serves all of those rows

#### Scenario: Search false positive

- WHEN ROR returns records but none contains the exact requested QID
- THEN the row is `abstained_not_found`
- AND `updates` is empty

#### Scenario: Conflicting stored parent names

- WHEN the same QID appears under two distinct nonblank parent names anywhere across the two affiliation stores
- THEN all selected rows using that QID are `blocked_qid_name_conflict`
- AND no ROR request is made for that QID

#### Scenario: Conflicting stored QIDs

- WHEN one parent name carries two distinct nonblank QIDs anywhere across the two affiliation stores
- THEN all selected position-1 rows using that parent name are `blocked_name_qid_conflict`
- AND no ROR request is made for either selected QID

#### Scenario: Missing QID

- WHEN a selected named affiliation has a blank or malformed `affiliation_wikidata_qid`
- THEN it is `blocked_missing_qid`
- AND the tool does not fall back to name matching

## Database application

Research mode MUST finish every ROR request and serialize the complete result set without opening a write transaction. Apply mode MUST load the reviewed report, validate its version and complete structure, reject unexpected statuses or update fields, and make no network request. The report is untrusted input: its values may become only parameterized database values, never paths, commands, SQL identifiers, identity-policy overrides, or log payloads.

The operator MUST make the repository-required timestamped database backup before invoking `--apply`; the command MUST print that prerequisite in its apply-mode start message but does not create or manage backups.

One short transaction MUST apply confirmed results by exact `award_record_id`. Each update MUST require all of the following current values to equal the researched snapshot:

- `award_record_id`;
- `affiliation_name`;
- `affiliation_wikidata_qid`; and
- blank `affiliate_ror`.

Each confirmed row MUST affect exactly one row. A zero-row or multi-row result indicates concurrent drift or a broken invariant; the command MUST roll back the whole batch and report failure. Nonconfirmed and unchanged results never enter the transaction. The command MUST not offer an overwrite option.

### Requirement: Blank-only guarded writes — apply mode MUST preserve every curated value

#### Scenario: Successful reviewed batch

- WHEN `--apply <report.json>` receives the reviewed preview and all confirmed rows still have their researched name, QID, and blank ROR cell
- THEN one transaction fills only `affiliate_ror`
- AND the JSON apply result reports the exact number of affected rows
- AND apply mode makes no ROR request

#### Scenario: Row changes after lookup

- WHEN a confirmed row's name, QID, or ROR cell changes before its guarded update
- THEN the transaction rolls back
- AND no row from that batch remains changed
- AND the command exits nonzero with a factual drift error

## Failure behavior and observability

In research mode, HTTP 429 MUST honor a valid `Retry-After` once; a repeated 429 fails. Other HTTP errors, URL errors, timeouts, invalid JSON, incomplete pages, and invalid response structures MUST fail visibly. In apply mode, a missing, unreadable, or structurally invalid report MUST fail before a transaction opens. The tool MUST NOT convert infrastructure failure into `abstained_not_found`.

Logs MUST identify the operation, safe QID or `award_record_id`, outcome, and next action without logging URL query strings or response bodies. QIDs and ROR IDs are public identifiers; no credentials or personal payloads are introduced.

ROR response scores MUST NOT be used. The command MUST NOT call the affiliation parameter, advanced query parameter, OpenAlex, a search engine, or a model fallback. These paths add ambiguity without improving the exact external-ID contract.

## Compatibility

The schema, row count, existing values, website behavior, and generated CSV headers remain unchanged. Successful enrichment changes only blank `affiliate_ror` cells. The website already reads and exports the field verbatim through `datasets/website/build.py:141-176,192-228,800-885,2501-2509`.

Rows that cannot be resolved safely remain blank. The report is the claim-level research handoff required by `AGENTS.md`; it MUST be retained with the run handoff because no dedicated provenance columns exist. The API is explicitly versioned as v2 so a future breaking API version cannot silently change parsing.

## Verification

Implementation verification MUST proceed in this order:

1. Record a before snapshot of row count, distinct `award_record_id` count, nonblank `affiliate_ror` count, and every pre-existing nonblank `affiliate_ror` value.
2. Run focused tests covering selector validation, both cross-store identity-conflict directions, active/inactive/withdrawn exact-QID classification, incomplete and malformed responses, compact-ID validation, request deduplication, network failure, report validation, blank-only updates, no-network apply, and full rollback on drift.
3. Run a preview against representative live rows, including one unique active QID, one missing QID, and one QID in the live `umbrella-qid` backlog; redirect and inspect the complete JSON review artifact.
4. Back up `awards.sqlite3` with the timestamped `.ror.bak` convention from the affiliation reference.
5. Apply the exact reviewed report artifact. For the research run that created it, pass every assigned `award_record_id` explicitly; use `--all` only when the curator explicitly authorizes the full backfill.
6. Confirm that the row count and distinct `award_record_id` count did not change, all pre-existing nonblank ROR values are byte-for-byte unchanged, and the number of newly nonblank cells equals the report's affected-row count.
7. Run `sqlite3 awards.sqlite3 "PRAGMA integrity_check;"` and require exactly `ok`.
8. Run `uv run scripts/validate_awards.py`, save the full before/after group output, and verify that no affiliation identity group was added or enlarged.
9. Run `uv run scripts/normalize_affiliations.py` in dry-run mode and inspect its report; do not apply unrelated normalization.
10. Run `uv run pytest tests/test_lookup_ror.py`, `uv run pytest tests/`, and `uv run ruff check`.
11. Run `uv run website/build.py --base-url https://example.org/awards/` as the final live-data gate.

The implementation SHALL follow the project instruction not to create a Git branch. Unit tests are part of implementation; no commit, push, merge, or deployment is requested.
