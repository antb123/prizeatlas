# Non-science move and restore implementation

Specification: `docs/specs/datasets-non-science-move-restore-20260731.md`

## Shared assumptions

1. **Load-bearing:** “Science/Math only” excludes exactly `History`, `Arts`, `Lit`, and `Economics`; all six other allowed `high_school_subject` values remain.
2. **Load-bearing:** The requested filenames `dump_arts.py` and `load_arts.py` remain for compatibility even though their scope expands to all four non-science subjects.
3. **Load-bearing:** A restore is insert-only; any existing dumped `award_record_id` or ranking primary key blocks the entire load.
4. **Load-bearing:** The move aborts if a selected award owns a row in `award_extra_affiliations`; the current live count is zero.
5. A new default dump path `non_science.json` avoids overwriting the existing Arts-only `arts.json`.
6. Generated dumps and timestamped backups remain local operational artifacts and are not versioned.
7. Work directly in the current branch because this repository explicitly does not use branches.

## Task DNM-1 — Ignore operational dumps

ID: DNM-1

Depends-on: none

Files: `.gitignore:1-15`

Steps → verify:

1. Add root-relative ignore entries for `/arts.json` and `/non_science.json`.
2. Run `git check-ignore -v arts.json non_science.json` from `datasets/` → verify both paths resolve to the new rules.
3. Run `git diff --check -- .gitignore` → verify no whitespace errors.

Relevant assumptions: 5, 6, 7.

## Task DNM-2 — Implement durable dump and removal

ID: DNM-2

Depends-on: none

Files: `scripts/dump_arts.py:1-61`

Steps → verify:

1. Replace the Arts-only constants and copy-only control path with the exact `non-science-awards-v1` contract in specification lines 28-60.
2. Reserve `non_science.json` by exclusive creation → verify an existing destination fails before backup or database access and remains unchanged.
3. Acquire `BEGIN IMMEDIATE`; verify the initial ranking/live-award QID invariant and the zero-extra-affiliation precondition → verify either mismatch rolls back, removes an unverified reserved output, and creates no backup.
4. Select the four excluded subjects and only ranking rows whose complete award set is removed → verify current copy-based data selects 467 awards and Q47170.
5. Create the pre-write snapshot with SQLite's backup API, exclusive naming, durability sync, integrity checking, and typed schema/row equality → verify a broken or conflicting backup aborts before deletion.
6. Serialize, digest, write, fsync, reread, and validate the dump before deletion → verify format, subjects, counts, schemas, typed rows, and SHA-256 match.
7. Delete exact dumped award and ranking primary keys, then prove retained awards, shared affiliations, and retained rankings are typed-cell equal to their pre-delete snapshots → verify `PRAGMA integrity_check` is `ok` before commit.
8. Exercise failure before and after dump verification → verify early failure removes only the newly reserved output, while later failure keeps the verified dump and backup and rolls back the database.
9. Run `uv run ruff check scripts/dump_arts.py` → verify lint passes.

Acceptance scenarios covered: successful move; existing destination; extra-affiliation ownership conflict; failure after durable dump creation.

Relevant assumptions: 1, 2, 4, 5, 6, 7.

## Task DNM-3 — Implement insert-only later restore

ID: DNM-3

Depends-on: DNM-2

Files: `scripts/load_arts.py:1-133`

Steps → verify:

1. Implement offline validation for the exact format, subjects, structure, recorded table schemas, counts, typed rows, primary keys, and canonical digest from specification lines 28-43 and 91-101.
2. Acquire `BEGIN IMMEDIATE`; compare live `PRAGMA table_info`, check all award/ranking conflicts, and check extra-affiliation ownership under the lock → verify second and partially overlapping loads roll back before backup creation.
3. Create and validate the durable pre-write backup through SQLite's backup API → verify its integrity and typed equality to the locked target state.
4. Insert awards first and ranking rows second with plain `INSERT` statements only → verify the code contains no update, delete, replace, or upsert path.
5. Select inserted rows back in canonical order, compare typed cells to the dump, verify row counts and the ranking/live-award invariant, and require `PRAGMA integrity_check = ok` before commit.
6. Force an insert or post-insert verification failure → verify all awards and ranking inserts roll back.
7. Run `uv run ruff check scripts/load_arts.py` → verify lint passes.

Acceptance scenarios covered: successful later restore; second or overlapping load; corrupt, incomplete, or incompatible dump.

Relevant assumptions: 1, 2, 3, 4, 5, 6, 7.

## Task DNM-4 — Prove the destructive workflow on copies

ID: DNM-4

Depends-on: DNM-1, DNM-2, DNM-3

Files: `tests/test_arts_dump.py:1-116`

Steps → verify:

1. Extend the fixture to model all four excluded subjects, all six retained subject values, `award_ranking`, `affiliations`, and `award_extra_affiliations`.
2. Add focused tests for every acceptance scenario named in DNM-2 and DNM-3, including rollback, digest/schema/value validation, backup correctness, output preservation, and conflict behavior.
3. Snapshot schemas and typed rows before the move → verify retained awards, shared affiliations, and retained rankings remain identical after removal, and dumped awards/ranking rows are identical after restoration.
4. Exercise concurrent or state-drift conflict paths → verify SQLite primary keys and the write transaction prevent duplicates and partial loads.
5. Run `uv run python -m unittest tests.test_arts_dump` → verify all focused tests pass.
6. Run `uv run ruff check scripts/dump_arts.py scripts/load_arts.py tests/test_arts_dump.py` → verify lint passes.
7. Copy the live database, run the move against that copy, and confirm 467 awards plus Q47170 are removed with integrity `ok`.
8. Build the static website from the moved copy with `uv run website/build.py --base-url https://example.org/awards/ --database <copy>` → verify the build succeeds with only the six retained subjects.
9. Restore the copy from its dump → verify all table schemas and typed rows equal the pre-move snapshot and integrity is `ok`.
10. Do not run the destructive move against live `datasets/awards.sqlite3` until steps 5-9 pass.

Acceptance scenarios covered: all specification scenarios, plus successful Science/Math-only website generation and complete typed-row round trip.

Relevant assumptions: 1, 2, 3, 4, 5, 6, 7.
