## Goals

Add `orc_id`, `affiliate_ror`, `author_openalex_id`, and `institution_openalex_id` as optional researcher and institution identifiers on every row of the authoritative `awards` table and on the static website's `AwardRecord` data model.

The change MUST preserve all 3,096 existing award rows, every existing value and `award_record_id`, and the current website behavior. A completed build SHALL carry all four new values through the read model and append them to the generated `awards.csv`; it shall not display them in HTML.

## Background

`datasets/awards.sqlite3` is the sole source of truth. Its `awards` table is `STRICT` and currently contains 32 columns (schema positions 0–31), one row per award recipient. It already stores the compact `laureate_wikidata_qid` identity at position 9, but has no OpenAlex or ORCID fields.

The website has no ORM or separate schema definition. `datasets/website/build.py:141-171` declares the selected database fields in `AWARD_COLUMNS`, `datasets/website/build.py:190-221` mirrors them positionally in the `AwardRecord` dataclass, `datasets/website/build.py:800-885` reads them, and `datasets/website/build.py:2501-2509` writes the same fields to the downloadable CSV.

The test database and record helper derive their columns from `AWARD_COLUMNS` (`datasets/tests/test_build_website.py:34-44,58-119`). The existing CSV test at `datasets/tests/test_build_website.py:1730-1763` is therefore the focused place to prove that nonblank identifier values survive the full database-read/export path.

## Assumptions

1. **Load-bearing:** `orc_id` stores the canonical hyphenated 16-digit ORCID form exemplified by `0000-0002-0254-0778`, without an `https://orcid.org/` prefix.
2. **Load-bearing:** `author_openalex_id` stores a compact OpenAlex Author ID such as `A1969205032`, and `institution_openalex_id` stores a compact OpenAlex Institution ID such as `I136199984`.
3. **Load-bearing:** `affiliate_ror` stores the compact ROR identifier such as `03vek6s52`, without an `https://ror.org/` prefix.
4. **Load-bearing:** The supplied ORCID is a format example only; no award row is assigned any identifier in this change because no laureate or `award_record_id` was specified.
5. The author fields are present on organization rows for a uniform row schema but remain blank. The institution fields describe the row's primary flat affiliation; extending them to `award_extra_affiliations` is out of scope.
6. Empty string is the repository's unset-value representation for newly appended text fields and MUST be the non-null default.
7. The fields are not unique at award-row level because one researcher or institution can occur on several award rows.
8. Identifier discovery, backfilling, validation, HTML display, linking, identity merging, and API access are out of scope.

## Scope

Estimated implementation: about 18 changed lines across 3 files, plus four SQLite `ALTER TABLE` statements.

| File | Current range | Required change |
|---|---:|---|
| `datasets/awards.sqlite3` | `awards` schema positions 0–31 | Append schema positions 32–35 with the four requested names; do not update row values. |
| `datasets/website/build.py` | `141-172`, `192-224` | Append the four names to `AWARD_COLUMNS` and matching string fields to `AwardRecord`. |
| `datasets/tests/test_build_website.py` | `1723-1774` | Give one fixture record all four identifiers and assert their names, order, and values in generated `awards.csv`. |

No template, enrichment script, validator, index, lookup table, route, or archived CSV changes are included.

## Data model

The live database MUST be backed up before either schema statement, following the repository's database safety rule. The migration then appends the fields in this order:

```sql
ALTER TABLE awards ADD COLUMN orc_id TEXT NOT NULL DEFAULT '';
ALTER TABLE awards ADD COLUMN affiliate_ror TEXT NOT NULL DEFAULT '';
ALTER TABLE awards ADD COLUMN author_openalex_id TEXT NOT NULL DEFAULT '';
ALTER TABLE awards ADD COLUMN institution_openalex_id TEXT NOT NULL DEFAULT '';
```

All four statements MUST run in one short transaction. The implementation MUST first inspect `PRAGMA table_info(awards)` and fail without writing if only some fields already exist or if an existing same-named field has a different type, nullability, or default. It MAY treat four correctly defined existing fields as an already-applied no-op.

No `UNIQUE`, `CHECK`, or ordinary index is added. A row-level uniqueness constraint would reject legitimate repeated researchers, and format validation or lookup behavior was not requested.

### Requirement: Optional fields on every row — all four identifier columns MUST exist with blank defaults

#### Scenario: Existing database receives the fields

- WHEN the four schema statements are applied to the current 3,096-row `awards` table
- THEN `PRAGMA table_info(awards)` reports `orc_id`, `affiliate_ror`, `author_openalex_id`, and `institution_openalex_id` as the final four `TEXT NOT NULL DEFAULT ''` columns
- AND the row count and all 3,096 existing `award_record_id` values remain unchanged
- AND every existing row has `''` in all four new fields

#### Scenario: Repeated researcher identifiers

- WHEN two award rows later carry the same ORCID, OpenAlex ID, or ROR ID
- THEN the schema accepts both rows

## Website record and export

`orc_id`, `affiliate_ror`, `author_openalex_id`, and `institution_openalex_id` MUST be appended, in that order, to `AWARD_COLUMNS` and to the required string fields of `AwardRecord` immediately before the defaulted `affiliations` field. Appending preserves every existing public CSV column position and matches SQLite's appended physical order.

The existing single control path MUST remain unchanged: `read_database` selects `AWARD_COLUMNS`, constructs `AwardRecord`, and `write_dataset_csv` emits `AWARD_COLUMNS`. No identifier-specific parsing, normalization, rendering, or branching is introduced.

### Requirement: Lossless model round trip — the website MUST retain identifier text verbatim

#### Scenario: Nonblank identifiers are exported

- WHEN a test award row contains representative nonblank values in all four new fields
- THEN `read_database` returns an `AwardRecord` with those exact values
- AND generated `awards.csv` appends headers `orc_id,affiliate_ror,author_openalex_id,institution_openalex_id` after all existing headers
- AND the same row contains all four exact values under those headers

#### Scenario: Blank identifiers do not change HTML

- WHEN all live rows have blank values in the four new fields
- THEN the static build succeeds without any template changes
- AND no identifier URL or label is added to generated HTML

## Compatibility and failure behavior

The downloadable `awards.csv` gains four trailing columns. This is an additive public schema change, not a compatibility guarantee: header-aware consumers can discover the new fields, while consumers that require the previous exact header width can break and must be updated. Existing column names, order, and values remain unchanged before the four-field append. The archived 26-column CSV snapshots under `datasets/old/` remain unchanged.

A pre-migration database lacks required selected columns and will continue to make the website build fail with SQLite's missing-column error. This is intentional: there is one authoritative database and no fallback schema or silent default path.

The implementation MUST preserve the user's existing uncommitted database and test changes. It must use targeted `ALTER TABLE` statements and a focused test edit; it must not rebuild `awards.sqlite3`, rewrite existing rows, or alter adjacent test expectations.

No new logging is required. SQLite command failure, a failed integrity check, or a failed focused test MUST propagate as a visible failure.

## Security and data handling

The fields are public researcher and institution identifiers and are exported only through the already-public dataset download. This change does not make network requests or accept untrusted identifiers as commands, paths, policy, or identity-merging keys.

Values remain opaque stored text. Future enrichment MUST verify ownership before assigning an identifier and is outside this change.

## Verification

Implementation verification MUST include:

1. Before and after schema comparison showing only `orc_id`, `affiliate_ror`, `author_openalex_id`, and `institution_openalex_id` were appended.
2. Attach the pre-change backup read-only and compare all original 32-column tuples in both directions; both set differences MUST return zero rows, proving every prior value and row was preserved.
3. Before and after checks showing the row count remains 3,096 and `COUNT(DISTINCT award_record_id)` remains 3,096.
4. `sqlite3 datasets/awards.sqlite3 "PRAGMA integrity_check;"` returning exactly `ok`.
5. A focused website test proving the nonblank values survive database read and CSV export.
6. `cd datasets && uv run python -m unittest tests.test_build_website.WebsiteBuildTests.test_dataset_csv_dumps_every_award_and_is_linked_from_every_footer`.
7. `cd datasets && uv run website/build.py --base-url https://example.org/awards/` to verify the live schema and blank defaults build successfully.

The implementation SHALL follow the project instruction not to create a Git branch. No commit, push, or merge is part of this request.
