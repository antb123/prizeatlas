## Goals

- `scripts/dump_arts.py` MUST move every award whose `high_school_subject` is `History`, `Arts`, `Lit`, or `Economics` from `awards.sqlite3` into one durable dump, leaving the live database suitable for a Science/Math-only website build.
- `scripts/load_arts.py` MUST restore every dumped award and its position-2+ affiliations later without updating, deleting, or duplicating any existing database row.
- Both operations MUST fail without partial database changes when their safety preconditions are not met.
- Verification SHALL prove the 467 current non-science awards can be removed and restored byte-for-byte on a database copy, with `PRAGMA integrity_check` returning `ok` after each write.

## Background

The current utilities export and restore only `high_school_subject = 'Arts'`: `scripts/dump_arts.py:12-36` writes 103 complete `awards` rows to an exclusive JSON file, while `scripts/load_arts.py:22-108` validates that file and inserts rows only when none of their primary keys exists. The live subject distribution is 143 `History`, 103 `Arts`, 122 `Lit`, and 99 `Economics` rows, for 467 non-science awards.

Dumping currently copies rows without removing them. A static website build is read-only, so the requested Science/Math-only website requires a deliberate move operation: create and durably flush a complete dump, back up the database, then delete exactly the dumped rows in a transaction.

Affiliations require separate handling. Position 1 is stored within each complete `awards` row. Positions 2+ are stored in `award_extra_affiliations`, keyed by `(award_record_id, position)`, as documented in `docs/datasets-affiliation-records-20260728.md:9-75`. The current 467-row selection has no extra-affiliation rows, but the dump format must preserve any that exist when a future dump is made. Shared institution profiles in `affiliations` and award-family metadata in `award_ranking` are not owned by one award row and remain untouched.

## Assumptions

1. **Load-bearing:** “Science/Math only” excludes exactly `History`, `Arts`, `Lit`, and `Economics`; all six other allowed `high_school_subject` values remain.
2. **Load-bearing:** The requested filenames `dump_arts.py` and `load_arts.py` remain for compatibility even though their scope expands to all four non-science subjects.
3. **Load-bearing:** A restore is insert-only; any existing dumped `award_record_id` or extra-affiliation primary key blocks the entire load.
4. A new default dump path `non_science.json` avoids overwriting the existing Arts-only `arts.json`.
5. The generated dump and timestamped backups remain local operational artifacts and are not versioned.
6. The project instruction not to use Git branches overrides generic branch-based delivery guidance.

## Dump and remove

Expected implementation: `scripts/dump_arts.py:1-61`, approximately 90 changed or added lines.

The script MUST select complete `awards` rows whose `high_school_subject` is one of the four values in Assumption 1, ordered by `award_record_id`. It MUST also select every `award_extra_affiliations` row owned by those award IDs, ordered by `(award_record_id, position)`. It MUST obtain column order from each live table rather than duplicating the 36-column award schema in code.

The versioned JSON document MUST contain:

- the exact four-subject vocabulary;
- ordered column names and rows for `awards`;
- ordered column names and rows for `award_extra_affiliations`;
- declared counts for both row sets;
- a SHA-256 digest over a canonical serialization of the schema, subject vocabulary, and both row sets.

The script MUST use exclusive output creation. If the destination exists, it MUST report failure before creating a backup or changing the database. The default destination SHALL be `datasets/non_science.json`.

Before deletion, the script MUST create a timestamped byte-for-byte database backup. It MUST then acquire a SQLite write transaction, select the dump content from that transaction's stable view, write and flush the dump to durable storage, delete owned `award_extra_affiliations` rows first, delete exactly the selected `awards` rows second, and run `PRAGMA integrity_check`. It MUST commit only when:

- the written dump can be read back;
- its declared counts and digest validate;
- deleted row counts equal dumped row counts;
- no selected award IDs remain;
- no extra-affiliation rows for selected award IDs remain;
- `PRAGMA integrity_check` returns exactly `ok`.

If writing, verification, deletion, or integrity checking fails, the database transaction MUST roll back. A completed dump may remain after a rolled-back database operation; rerunning MUST refuse to overwrite it so an operator can inspect it and the backup.

The script MUST log only paths, stable operation names, counts, outcome, and the backup path. It MUST NOT print award contents.

### Requirement: Exact non-science move — The dump MUST precede transactional removal

#### Scenario: Successful move

- WHEN the destination does not exist and the live database contains the current 467 non-science awards
- THEN the dump contains all 467 complete award rows and all owned extra affiliations
- AND the database retains no `History`, `Arts`, `Lit`, or `Economics` awards
- AND every other award, `affiliations` row, and `award_ranking` row is unchanged
- AND database integrity is `ok`

#### Scenario: Existing destination

- WHEN the destination already exists
- THEN the command fails
- AND the destination and database remain byte-for-byte unchanged

#### Scenario: Failure after dump creation

- WHEN dump verification, deletion, or integrity checking fails
- THEN the database transaction rolls back completely
- AND the pre-operation database backup remains available

## Restore

Expected implementation: `scripts/load_arts.py:1-133`, approximately 80 changed or added lines.

The loader MUST accept only the new versioned non-science format. Before creating a backup or opening a write transaction, it MUST validate:

- the exact subject vocabulary from Assumption 1;
- unique column names matching the live `awards` and `award_extra_affiliations` schemas exactly and in order;
- row widths and SQLite-compatible text/null values;
- unique, nonblank `award_record_id` values;
- each award row's `high_school_subject`;
- every extra-affiliation row's ownership by a dumped award ID;
- unique `(award_record_id, position)` pairs;
- declared counts;
- the payload digest.

The loader MUST fail before writing if any dumped `award_record_id` already exists or any dumped `(award_record_id, position)` conflicts. This rule also makes a second load and a partially overlapping load safe. SQLite primary keys provide a second enforcement layer if database state changes after preflight.

After validation, the loader MUST create a timestamped database backup. In one `BEGIN IMMEDIATE` transaction it MUST insert awards first, insert extra affiliations second, verify inserted counts, and run `PRAGMA integrity_check`. Any failure MUST roll back all inserts. It MUST never issue `UPDATE`, `DELETE`, `INSERT OR REPLACE`, or an upsert.

### Requirement: Reversible restore — The loader MUST restore the dump without overwriting live data

#### Scenario: Successful later restore

- WHEN none of the dumped primary keys exists and the schemas still match
- THEN all awards and owned extra affiliations are inserted
- AND the restored rows equal the dumped rows
- AND database integrity is `ok`

#### Scenario: Second or overlapping load

- WHEN one or more dumped primary keys already exists
- THEN the loader fails with a conflict count
- AND no row is inserted, updated, or deleted
- AND no load backup is created because the failure occurs during preflight

#### Scenario: Corrupt or incomplete dump

- WHEN counts, row ownership, schemas, subject values, or the digest do not validate
- THEN the loader fails before any database write

## Website workflow

The scripts MUST NOT invoke the website builder. After a successful move, the existing command remains:

`uv run website/build.py --base-url https://example.org/awards/`

Because `website/build.py` reads `awards.sqlite3` without modifying it, the generated site will contain only the six retained Science/Math subject groups until the dump is restored. After a successful restore, rebuilding the website will include all ten subjects again.

## Tests and verification

Expected implementation: `tests/test_arts_dump.py:1-116`, approximately 120 changed or added lines. Total expected implementation scope is three files and approximately 290 changed or added lines; no implementation TODO is required.

Focused tests MUST cover:

- selection and removal of all four non-science subjects while science rows remain byte-for-byte unchanged;
- round-trip equality for all award columns;
- round-trip preservation of zero, one, and multiple extra-affiliation rows;
- refusal to overwrite an existing dump;
- rollback when dump verification or deletion fails;
- refusal of malformed schemas, mismatched counts, invalid subjects, orphan extras, duplicate keys, and bad digests;
- successful insert-only restoration;
- refusal of second and partially overlapping loads without any database change;
- rollback of all awards and extras when one insert fails;
- database backups on write paths and no backups on preflight failures;
- `PRAGMA integrity_check = ok`.

Final verification MUST run:

- `uv run python -m unittest tests.test_arts_dump`
- `uv run ruff check scripts/dump_arts.py scripts/load_arts.py tests/test_arts_dump.py`
- a copy-based live-data drill that dumps/removes 467 rows, confirms only the six retained subjects remain, restores 467 rows, compares restored rows and extras to the pre-operation copy, and confirms integrity after both writes.

The live `datasets/awards.sqlite3` MUST NOT be modified until the copy-based drill passes.
