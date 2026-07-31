## Goals

Define a small enrichment pass that fills blank `orc_id` and `author_openalex_id` cells with the most accurate data available from each laureate's existing Wikidata QID.

The pass MUST fill blank cells only, MUST never identify a researcher by name, and MUST leave a field blank when the linked sources are missing, invalid, or contradictory.

## Background

`datasets/awards.sqlite3` is the source of truth. It contains 3,047 individual award rows, all with a `laureate_wikidata_qid`. Those rows represent 2,332 distinct individual QIDs. Every `orc_id` and `author_openalex_id` cell is currently blank.

Wikidata stores ORCID in `P496` and OpenAlex IDs in `P10283`. A read-only audit found `P496` on 573 distinct laureate QIDs, `P10283` on 35, and both on 17. OpenAlex can also retrieve one author directly by ORCID, so `P496` is the useful primary path for filling both fields.

Relevant contracts:

- Wikidata `P496`: https://www.wikidata.org/wiki/Property:P496
- Wikidata `P10283`: https://www.wikidata.org/wiki/Property:P10283
- OpenAlex single-author lookup: https://developers.openalex.org/api-reference/authors/get-a-single-author

## Assumptions

1. **Load-bearing:** `laureate_wikidata_qid` is the identity key; the pass never searches by name.
2. **Load-bearing:** `orc_id` comes from one valid effective Wikidata `P496` value.
3. **Load-bearing:** `author_openalex_id` comes from an exact OpenAlex author lookup by ORCID or a valid author-form `P10283`.
4. **Load-bearing:** Existing nonblank values are never overwritten.
5. **Load-bearing:** Multiple or contradictory identifiers leave the affected field blank.
6. Deprecated Wikidata claims are ignored; a preferred claim takes precedence over normal claims.
7. Organizations receive neither identifier.
8. Repeated award rows with the same QID receive the same confirmed values.

## Scope

Estimated implementation: about 350 lines across three files, plus blank-only data updates.

| File | Current range | Required change |
|---|---:|---|
| `datasets/scripts/lookup_authors.py` | New file | Read exact QIDs, retrieve and validate identifiers, report results, and optionally apply blank-only updates. |
| `datasets/tests/test_lookup_authors.py` | New file | Test claim selection, validation, exact OpenAlex lookup, conflicts, and blank-only writes. |
| `datasets/awards.sqlite3` | `awards.laureate_wikidata_qid`, schema positions `32` and `34` | Fill confirmed blank `orc_id` and `author_openalex_id` cells only. |

No schema, website, template, affiliation, citation-metric, name-matching, or existing enrichment-script change is included.

## Lookup behavior

The command MUST require `--db awards.sqlite3` and either repeatable exact `--record-id` selectors or explicit `--all`. Without `--apply`, it prints a JSON preview and does not write. With `--apply`, it finishes all lookups before opening one short database transaction.

For each distinct selected individual QID:

1. Retrieve `P496` and `P10283` from Wikidata.
2. Ignore deprecated claims and prefer a preferred-rank claim over normal-rank claims.
3. Accept `P496` only when exactly one effective value has canonical ORCID format and a valid checksum.
4. Accept `P10283` only when exactly one effective value has OpenAlex author form.
5. When a valid ORCID exists, query OpenAlex directly by that ORCID.
6. When a valid `P10283` exists, query OpenAlex directly by that author ID.
7. Use the OpenAlex response only when its returned author ID and ORCID agree with the exact lookup input.

The pass MUST NOT use names, affiliations, works, topics, citation counts, or search result ranking to choose an identity.

### Requirement: ORCID fill — one valid `P496` MUST fill blank `orc_id`

#### Scenario: One valid claim

- WHEN an individual QID has one valid effective `P496`
- THEN that ORCID is proposed for every selected blank `orc_id` row with the same QID

#### Scenario: Missing or ambiguous claim

- WHEN `P496` is missing, malformed, or has multiple effective values
- THEN `orc_id` remains blank

### Requirement: OpenAlex fill — only an exact author lookup MUST fill `author_openalex_id`

#### Scenario: ORCID resolves exactly

- WHEN OpenAlex retrieves one author by the valid `P496` value
- AND the response echoes the same ORCID
- THEN the returned compact author ID is proposed

#### Scenario: Direct `P10283` resolves exactly

- WHEN a valid author-form `P10283` retrieves the same OpenAlex author ID
- THEN that compact author ID is proposed

#### Scenario: Sources disagree

- WHEN the ORCID path and `P10283` path return different author IDs or ORCIDs
- THEN `author_openalex_id` remains blank
- AND the conflict is reported

#### Scenario: OpenAlex has no author

- WHEN exact OpenAlex lookup returns not found
- THEN `author_openalex_id` remains blank
- AND a valid `P496` may still fill `orc_id`

## Database writes

Research MUST complete before a write transaction begins. Apply MUST update by exact `award_record_id` and matching `laureate_wikidata_qid`, and every assignment MUST be guarded so a nonblank cell cannot be overwritten.

Before writing, the pass MUST reject a proposed identifier that maps to more than one QID in the current database or current result set. Repeated rows for one QID are valid.

The JSON output MUST include each selected `award_record_id`, QID, status, source URLs, proposed updates, and a concise reason. Network or malformed-response failures MUST stop the run visibly instead of silently producing partial research.

### Requirement: Blank-only updates — curated values MUST remain unchanged

#### Scenario: Successful apply

- WHEN all confirmed target cells remain blank and their QIDs are unchanged
- THEN one transaction writes only the proposed identifier cells

#### Scenario: Row changed after research

- WHEN a target cell or QID changes before its guarded update
- THEN the transaction rolls back
- AND no row from the batch remains changed

## Verification

Implementation verification MUST include:

1. Focused tests for claim rank, ORCID format and checksum, author-ID format, missing and multiple claims, exact OpenAlex responses, source disagreement, repeated QIDs, organizations, identifier collisions, and guarded rollback.
2. `uv run pytest tests/test_lookup_authors.py`.
3. A dry run against representative live rows before any write.
4. A timestamped `awards.sqlite3` backup before apply.
5. Exact before/after confirmation that only reported blank `orc_id` and `author_openalex_id` cells changed.
6. `sqlite3 awards.sqlite3 "PRAGMA integrity_check;"` returning exactly `ok`.
7. `uv run scripts/validate_awards.py`.
8. `uv run pytest tests/` and `uv run ruff check`.
9. `uv run website/build.py --base-url https://example.org/awards/`.

The implementation SHALL follow the project instruction not to create a Git branch. This specification changes no code or database data.
