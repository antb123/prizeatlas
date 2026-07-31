## Goals

- `scripts/dump_arts.py` MUST move every award whose `high_school_subject` is `History`, `Arts`, `Lit`, or `Economics` from `awards.sqlite3` into one durable dump, leaving a database from which the static Science/Math-only website builds successfully.
- `scripts/load_arts.py` MUST restore every dumped award and temporarily removed ranking row later without updating, deleting, or duplicating any existing row.
- Both operations MUST fail without partial database changes when their safety preconditions are not met.
- Verification SHALL prove the 467 current non-science awards can be removed and restored with typed cell equality on a database copy, with `PRAGMA integrity_check` returning `ok` after each write.

## Background

The current utilities handle only `high_school_subject = 'Arts'`: `scripts/dump_arts.py:12-36` copies 103 complete `awards` rows to an exclusive JSON file, while `scripts/load_arts.py:22-108` validates that file and inserts rows only when none of their primary keys exists. The live distribution is 143 `History`, 103 `Arts`, 122 `Lit`, and 99 `Economics` rows, for 467 non-science awards.

A static website build is read-only, so dumping alone cannot produce the requested view. The move operation must reserve and durably write a complete dump, take a consistent database backup, and then delete exactly the dumped rows in one transaction.

Removing all 99 Economics awards also leaves the `award_ranking` row for Q47170 without a live award. `website/build.py:2396-2413` requires the ranking-QID set to equal the live-award-QID set and otherwise raises `BuildFailure`. The move must therefore dump and temporarily delete that one now-orphaned ranking row; the authoritative `award_ranking.toml` remains unchanged.

Position-1 affiliations live inside the complete `awards` rows. Positions 2+ live in `award_extra_affiliations`, whose exclusive source is `award_extra_affiliations.tsv`, as documented in `docs/datasets-affiliation-records-20260728.md:79-111`. The current 467 selected awards own zero extra-affiliation rows. To avoid creating a second source of truth, the move MUST abort if this precondition changes rather than dumping or deleting extra-affiliation rows. Shared institution profiles in `affiliations` remain untouched.

## Assumptions

1. **Load-bearing:** “Science/Math only” excludes exactly `History`, `Arts`, `Lit`, and `Economics`; all six other allowed `high_school_subject` values remain.
2. **Load-bearing:** The requested filenames `dump_arts.py` and `load_arts.py` remain for compatibility even though their scope expands to all four non-science subjects.
3. **Load-bearing:** A restore is insert-only; any existing dumped `award_record_id` or ranking primary key blocks the entire load.
4. **Load-bearing:** The move aborts if a selected award owns a row in `award_extra_affiliations`; the current live count is zero.
5. A new default dump path `non_science.json` avoids overwriting the existing Arts-only `arts.json`.
6. Generated dumps and timestamped backups remain local operational artifacts and are not versioned.
7. The project instruction not to use Git branches overrides generic branch-based delivery guidance.

## Dump format

Expected implementation: `scripts/dump_arts.py:1-61` and `scripts/load_arts.py:1-133`, approximately 80 shared format-validation lines.

The UTF-8 JSON document MUST use this top-level contract:

- `format`: the literal string `non-science-awards-v1`;
- `subjects`: the ordered list `["History", "Arts", "Lit", "Economics"]`;
- `tables.awards` and `tables.award_ranking`, each containing `schema`, `count`, and `records`;
- `sha256`: a lowercase hexadecimal digest.

Each `schema` MUST record every tuple returned by `PRAGMA table_info(<table>)`—column ID, name, declared type, not-null flag, default SQL, and primary-key position—in live column order. Each `records` list MUST use that same column order. `awards` records MUST be ordered by `award_record_id`; dumped `award_ranking` records MUST be ordered by `award_wikidata_qid`.

The digest input MUST be the entire document without `sha256`, serialized with `json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")`. The loader MUST recompute and compare the digest before opening the target database.

Before selecting ranking rows, the move MUST require exact equality between the live `award_ranking.award_wikidata_qid` set and the distinct nonblank `awards.award_wikidata_qid` set. A pre-existing mismatch MUST abort the operation. The dump MUST contain all 467 complete `awards` rows selected by Assumption 1 and only those ranking rows whose entire live award set is selected for removal; current data yields only Q47170. Declared counts MUST equal list lengths.

## Dump and remove

Expected implementation: `scripts/dump_arts.py:1-61`, approximately 130 changed or added lines.

The script MUST use exclusive creation to atomically reserve the output path. If it already exists, the command MUST fail before creating a backup or touching the database. The default destination SHALL be `datasets/non_science.json`.

With the reserved output open, the script MUST acquire `BEGIN IMMEDIATE` before reading live schemas, checking the ranking and extra-affiliation preconditions, selecting records, or creating the backup. Before any database write, it MUST create the backup exclusively from that locked, pre-write state through SQLite's backup API, never by copying only the main database file; flush and `fsync` the backup; verify its `PRAGMA integrity_check`; and verify its relevant schemas and typed table contents equal the locked source state.

The script MUST then build the document, write it into the reserved file, flush it, call `os.fsync()` on the file descriptor, `fsync` the parent directory, read the file back, and validate its format, counts, schemas, records, and digest. Only after that durable verification may it delete:

1. exactly the dumped `awards` rows, by their primary keys;
2. exactly the dumped `award_ranking` rows, by their primary keys.

The transaction MUST confirm deleted counts equal dumped counts, no dumped primary key remains, retained `awards` rows are typed-cell equal to their pre-delete snapshot, `affiliations` is typed-cell equal to its pre-delete snapshot, remaining `award_ranking` rows are typed-cell equal to their pre-delete snapshot, and `PRAGMA integrity_check` returns exactly `ok` before commit.

If failure occurs before the dump passes read-back verification, the transaction MUST roll back and the script MUST remove only the output file it exclusively created. If failure occurs after the dump is verified, the transaction MUST roll back but the verified dump and backup MUST remain for inspection. The script MUST log only operation names, paths, counts, outcomes, and the backup path; it MUST NOT print row contents.

### Requirement: Exact non-science move — The durable dump MUST precede transactional removal

#### Scenario: Successful move

- WHEN the destination does not exist, no selected award has an extra affiliation, and the database contains the current 467 non-science awards
- THEN the dump contains all 467 complete award rows and the Q47170 ranking row
- AND the database retains none of the four excluded subjects or their orphaned ranking rows
- AND retained awards, shared affiliations, and retained ranking rows are unchanged by typed cell comparison
- AND database integrity is `ok`

#### Scenario: Existing destination

- WHEN the destination already exists
- THEN the command fails
- AND the destination and database remain byte-for-byte unchanged
- AND no backup is created

#### Scenario: Extra-affiliation ownership conflict

- WHEN a selected award owns any `award_extra_affiliations` row
- THEN the command fails before backup or dump population
- AND no database row changes

#### Scenario: Failure after durable dump creation

- WHEN deletion or integrity checking fails after dump verification
- THEN the database transaction rolls back completely
- AND the verified dump and pre-operation backup remain available

## Restore

Expected implementation: `scripts/load_arts.py:1-133`, approximately 120 changed or added lines.

Before opening the database, the loader MUST validate the literal format identifier, exact subject list, payload structure, declared counts, row widths, unique nonblank primary keys, allowed subject values, value types, and digest. Award values MUST be text or null because the live `awards` schema is entirely TEXT. Ranking values MUST match the types and nullability declared by the recorded `PRAGMA table_info` schema, including the integer `score`.

The loader MUST then acquire `BEGIN IMMEDIATE` and, under that lock, validate exact `PRAGMA table_info` equality for both tables, confirm every dumped primary key is absent, and confirm no `award_extra_affiliations` row names a dumped award ID. A conflict MUST roll back before backup creation, so a second or partially overlapping load writes nothing and creates no backup.

After locked preflight, the loader MUST create and validate a durable snapshot backup through SQLite's backup API using the same requirements as the dump path. In the existing transaction it MUST insert awards first and ranking rows second. It MUST then select each inserted set in canonical order and compare typed cells with the payload, verify inserted counts, confirm the ranking-QID set equals the live-award-QID set, and require `PRAGMA integrity_check = ok` before commit.

The loader MUST never issue `UPDATE`, `DELETE`, `INSERT OR REPLACE`, or an upsert. Any failure MUST roll back all inserts.

### Requirement: Reversible restore — The loader MUST restore the dump without overwriting live data

#### Scenario: Successful later restore

- WHEN none of the dumped primary keys exists, schemas match, and no extra-affiliation row conflicts
- THEN all dumped awards and ranking rows are inserted
- AND restored rows equal dumped rows by typed cell comparison
- AND the ranking/live-award invariant holds
- AND database integrity is `ok`

#### Scenario: Second or overlapping load

- WHEN one or more dumped primary keys already exists
- THEN the loader fails with a conflict count
- AND no row is inserted, updated, or deleted
- AND no load backup is created

#### Scenario: Corrupt, incomplete, or incompatible dump

- WHEN format, subjects, counts, schemas, value types, primary keys, or digest do not validate
- THEN the loader fails before any database write

## Website workflow

The scripts MUST NOT invoke the website builder. After a successful move, the existing command remains:

`uv run website/build.py --base-url https://example.org/awards/`

The generated site will contain only the six retained Science/Math subject groups. `award_ranking.toml` MUST NOT be reloaded during this temporary state because its complete seed would restore Q47170 before its awards and make the build fail. After `load_arts.py` restores the dump, rebuilding the website will include all ten subjects again.

## Tests and verification

Expected implementation:

- `tests/test_arts_dump.py:1-116`, approximately 150 changed or added lines;
- `.gitignore:1-15`, two added ignore entries for `/arts.json` and `/non_science.json`.

Total expected implementation scope is four files and approximately 400 changed or added lines. The implementation TODO is `docs/datasets-non-science-move-restore-todo-20260731.md`.

Focused tests MUST cover:

- selection and removal of all four non-science subjects while retained awards remain typed-cell equal;
- selection/removal and restoration of an orphaned ranking row;
- a successful website-plan build from the moved database;
- refusal to overwrite an existing dump;
- refusal when a selected award has an extra affiliation;
- exclusive output cleanup before verification and preservation after verification;
- dump and backup flush/fsync calls;
- backup integrity and equality to the locked pre-write state;
- rollback when dump verification, deletion, or insertion fails;
- refusal of malformed table schemas, mismatched counts, invalid subjects, invalid value types, duplicate keys, and bad digests;
- successful insert-only restoration with typed-cell equality;
- refusal of second, concurrent, and partially overlapping loads without database changes;
- unchanged shared `affiliations`, retained `award_ranking`, indexes, and triggers;
- `PRAGMA integrity_check = ok`.

Final verification MUST run:

- `uv run python -m unittest tests.test_arts_dump`
- `uv run ruff check scripts/dump_arts.py scripts/load_arts.py tests/test_arts_dump.py`
- a copy-based live-data drill that moves 467 awards and Q47170, builds the static website from that database copy, restores the dump, compares all table schemas and typed rows with the pre-operation snapshot, and confirms integrity after both writes.

The live `datasets/awards.sqlite3` MUST NOT be modified until the copy-based drill and website build pass.
