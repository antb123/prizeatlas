## Goals

Fill blank position-1 `awards.institution_openalex_id` cells from the row's curated `affiliate_ror`.

A row MUST be writable only when OpenAlex returns one institution whose `ror` exactly equals
`https://ror.org/<affiliate_ror>`. The command must preview an explicit batch, apply only that reviewed report, preserve
every existing value, and leave the database healthy.

## Background

`awards.sqlite3` is the source of truth. It has 3,096 rows; 2,503 carry `affiliate_ror`, and all
`institution_openalex_id` cells are blank. The field is `TEXT NOT NULL DEFAULT ''` at schema position 35 and describes
only the flat position-1 affiliation.

OpenAlex accepts a ROR URL at `/institutions/{id}` and returns a singleton institution object. The only fields needed are
`id`, `display_name`, and `ror`. The existing ROR lookup establishes the selection, identity-conflict, report, and
blank-only apply patterns this command follows.

## Assumptions

1. **Load-bearing:** Store a compact OpenAlex Institution ID such as `I136199984`.
2. **Load-bearing:** Write only `awards.institution_openalex_id`; extra affiliations remain out of scope.
3. **Load-bearing:** An exact response ROR echo is the only writable match; names never establish identity.
4. **Load-bearing:** The existing two-store QID/name conflict gates block lookup.
5. **Load-bearing:** Read optional `OPENALEX_API` from `datasets/.env`; missing or blank means no API key.
6. **Load-bearing:** `--all` selects only rows with nonblank ROR and blank OpenAlex ID.
7. `blocked_missing_ror` and `unchanged` occur only for explicit `--record-id` selections.
8. The data run waits for curator-supplied record IDs or explicit authorization to use `--all`.

## Scope

Estimated implementation: about 450 lines across four files, plus reviewed database updates.

| File | Current range | Required change |
|---|---:|---|
| `datasets/scripts/lookup_openalex.py` | New file | Add preview and guarded apply. |
| `datasets/tests/test_lookup_openalex.py` | New file | Test selection, lookup, reports, and rollback. |
| `datasets/docs/datasets-affiliation-records-20260728.md:36-72,238-316` | Current documentation | Document field ownership and operation. |
| `datasets/awards.sqlite3` | `awards.institution_openalex_id`, position 35 | Fill confirmed blanks only. |

No schema, website, normalizer, ROR lookup, extra-affiliation, ORCID, author OpenAlex, or name-matching change is included.
The companion implementation plan is `datasets/docs/specs/datasets-affiliation-openalex-lookup-todo-20260730.md`.

## Command

Run from `datasets/`:

```text
uv run scripts/lookup_openalex.py --db awards.sqlite3 --record-id <id> [--record-id <id> ...]
uv run scripts/lookup_openalex.py --db awards.sqlite3 --all
uv run scripts/lookup_openalex.py --db awards.sqlite3 --apply <report.json>
```

Exactly one operation is required. Duplicate or unknown record IDs MUST fail before network access.

`--all` selects only rows where `affiliate_ror <> '' AND institution_openalex_id = ''`. An explicit `--record-id` may
instead report a missing ROR or an already populated OpenAlex ID.

Research writes one JSON document to stdout and progress to stderr. Apply makes no OpenAlex request.

## Lookup

Before network access, read position 1 and `award_extra_affiliations` as one relation. Block a selected row when:

- its name or QID is missing;
- its QID occurs under several nonblank parent names; or
- its parent name occurs under several nonblank QIDs.

For each remaining distinct ROR:

1. Validate `^0[a-hj-km-np-tv-z0-9]{6}[0-9]{2}$`.
2. Request `https://api.openalex.org/institutions/https://ror.org/<ror>` with
   `select=id,display_name,ror`, an identifying user agent, and a finite timeout.
3. Add `api_key=<OPENALEX_API>` only when `datasets/.env` supplies a nonblank value.
4. Wait at least 100 ms between uncached requests.
5. Retry one HTTP 429 with a valid `Retry-After`; fail on another 429.

Reuse one response for every selected row sharing that ROR.

Classify results as follows:

| Result | Status | Update |
|---|---|---|
| HTTP 200, exact ROR echo, valid `https://openalex.org/I<digits>` ID | `confirmed` | compact institution ID |
| HTTP 404 | `abstained_not_found` | none |
| HTTP 200, valid object, wrong ROR echo | `abstained_not_found` | none |
| Existing OpenAlex ID on an explicit row | `unchanged` | none |
| Missing or malformed ROR on an explicit row | `blocked_missing_ror` | none |
| Malformed JSON/object/ID, transport error, or other HTTP error | command failure | none |

Name differences are review information only and never rewrite stored affiliation data.

### Requirement: Exact ROR echo — only an exact OpenAlex crosswalk MUST be writable

#### Scenario: Exact match

- WHEN OpenAlex returns a valid institution object whose `ror` equals the requested ROR URL
- THEN the row is `confirmed`
- AND `updates` contains only the compact `institution_openalex_id`

#### Scenario: No exact match

- WHEN OpenAlex returns HTTP 404 or a valid object with a different `ror`
- THEN the row is `abstained_not_found`
- AND `updates` is empty

## Report

The preview is a versioned JSON object containing the database path, mode, processed count, status totals, and results.
Every result contains the snapshotted `award_record_id`, `affiliation_name`, `affiliation_wikidata_qid`, `affiliate_ror`,
and `institution_openalex_id`, plus its status, reason, and `updates`.

An attempted lookup also contains:

- `request_url`, without the API key; and
- `openalex_record`: `{id, display_name, ror}` for HTTP 200, or `null` for HTTP 404.

Allowed statuses are `confirmed`, `blocked_missing_name`, `blocked_missing_qid`, `blocked_missing_ror`,
`blocked_qid_name_conflict`, `blocked_name_qid_conflict`, `abstained_not_found`, and `unchanged`.

## Apply

The operator MUST create `awards.sqlite3.$(date +%Y%m%d-%H%M%S).openalex.bak` before apply.

Apply strictly validates the reviewed report and writes confirmed results in one transaction. Each parameterized update
matches:

- exact `award_record_id`;
- researched `affiliation_name`;
- researched `COALESCE(affiliation_wikidata_qid, '')`;
- researched `affiliate_ror`; and
- blank `institution_openalex_id`.

For a confirmed result, `openalex_record.ror` MUST equal the snapshotted ROR URL and
`updates.institution_openalex_id` MUST equal the compact suffix of `openalex_record.id`.

Each confirmed result MUST affect one row. Any drift rolls back the whole batch. There is no overwrite option.

### Requirement: Guarded apply — reviewed updates MUST remain blank-only

#### Scenario: Database drift

- WHEN any confirmed row no longer matches its researched snapshot
- THEN apply rolls back the complete batch
- AND exits nonzero

## Compatibility and security

Successful enrichment changes only blank `institution_openalex_id` values. Existing website behavior and CSV headers do
not change. Reports are the claim-level provenance handoff and must be retained.

The API key must never appear in stdout, stderr, reports, or errors. Response bodies are reduced to the three named public
fields. No branch, commit, push, merge, or deployment is part of implementation.

## Verification

1. Save row counts, distinct IDs, all nonblank OpenAlex values, and full validator output.
2. Run `uv run pytest tests/test_lookup_openalex.py`.
3. Create and inspect a preview for the curator-authorized scope.
4. Back up the database and verify the backup opens.
5. Apply that exact report without another lookup.
6. Prove row counts and prior values are unchanged and new values equal the affected count.
7. Require `PRAGMA integrity_check` to return `ok`.
8. Diff full `validate_awards.py` output and inspect the affiliation normalizer dry-run.
9. Run `uv run pytest tests/` and `uv run ruff check`; report unrelated existing failures without fixing them.
10. Run `uv run website/build.py --base-url https://example.org/awards/`.

No data preview or apply may run until the curator supplies record IDs or explicitly authorizes `--all`.
