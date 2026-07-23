## Implementation tasks

### ID: CSV-00 — Capture immutable conversion baselines

Depends-on: none

Files: all 12 top-level CSV files listed in the specification; all files under the repo-root `trash/` (read-only).

Steps → verify:

1. Using the documented safe-directory override, create and switch to the specification's implementation branch before changing any dataset.
2. Create a temporary, outside-the-worktree baseline containing each active CSV's exact header, parsed row count, row order, mapped values,
   and nonempty counts for every unmapped field.
3. In the same baseline, retain the repo-relative file list and content hash of every file under the repo-root `trash/`.
4. Assert every active input header and row count matches the exact contracts in the specification before permitting any conversion task to start.
5. Report the temporary baseline location for CSV-01 through CSV-04; do not modify any dataset or repo-root `trash/` file.

Relevant assumptions: 1, 4, 5, 6, 8.

### ID: CSV-01 — Normalize standalone compact award datasets

Depends-on: CSV-00

Files: `abel_prize.csv` lines 1-30; `japan_prize.csv` lines 1-117; `kyoto_prize.csv` lines 1-130;
`lasker_awards.csv` lines 1-424; `max_planck_medal.csv` lines 1-91; `shaw_prize.csv` lines 1-122;
`turing_award.csv` lines 1-82; `wolf_prize.csv` lines 1-392.

Steps → verify:

1. Load the CSV-00 baseline for each owned file and stop visibly if any current input differs.
2. Convert each row using `year → year`, `source → prize`, `rationale → motivation`, `laureate → full_name`,
   `country → birth_country`, and `source → source`; additionally map Lasker `category → category` and Wolf `field → category`.
3. Leave all unavailable canonical fields, including `location_research` and `location_birth`, empty and retain field text exactly.
4. Emit the required per-file conversion report, then parse each output and assert the exact canonical header, 22 fields per row,
   unchanged row count/order, and equality of every mapped nonempty value.

Relevant assumptions: 1, 2, 3, 4, 5, 6, 7, 8.

### ID: CSV-02 — Normalize enriched Breakthrough and Crafoord datasets

Depends-on: CSV-00

Files: `breakthrough.csv` lines 1-131; `crafoord.csv` lines 1-83.

Steps → verify:

1. Load the CSV-00 baselines and stop visibly if either current input differs.
2. Assert the baseline nonempty counts are 80/79 for Breakthrough and 81/81 for Crafoord; stop visibly if they differ.
3. Convert both static datasets using the specification table without invoking or restoring a generator.
4. Leave `location_research` and `location_birth` empty, and drop `birth_info` and `birth_year` only after retaining their per-file counts in the required conversion reports.
5. Assert exact canonical headers, 22 fields per row, 130 Breakthrough rows, 82 Crafoord rows, unchanged order, equality of mapped values,
   and an unchanged repo-root `trash/` file list and hash set.

Relevant assumptions: 1, 2, 3, 4, 5, 6, 7, 8.

### ID: CSV-03 — Normalize Fields and Nobel datasets

Depends-on: CSV-00

Files: `fields.csv` lines 1-69; `nobel.csv` lines 1-1027.

Steps → verify:

1. Load the CSV-00 baselines and stop visibly if either current input differs.
2. Convert Fields rows using `laureate → full_name`, `sex → sex`, `country → birth_country`, `birth_year → birth_date`,
   `affiliation → organization_name`, and the shared mappings; report and then drop `remarks`.
3. Preserve all existing `nobel.csv` values; append empty `source`, `location_research`, and `location_birth` fields to Nobel, and leave both location fields empty in Fields.
4. Emit the required per-file conversion reports and assert exact canonical headers, 22 fields per row, 68 Fields rows, 1026 Nobel rows,
   unchanged order, equality of mapped values, and the expected single nonempty dropped `remarks` value.

Relevant assumptions: 1, 2, 3, 4, 5, 6, 7, 8.

### ID: CSV-04 — Run cross-dataset acceptance checks

Depends-on: CSV-01, CSV-02, CSV-03

Files: all 12 top-level CSV files listed in the specification.

Steps → verify:

1. Parse all CSVs and assert the exact ordered canonical header and 22 fields in every row.
2. Assert each expected row count from the specification.
3. Review per-file conversion summaries for every unmapped input field and confirm row-count and mapped-value preservation with no silent unmapped-data loss.
4. Assert `location_research` and `location_birth` are empty in every row.
5. Compare the CSV-00 and post-conversion repo-root `trash/` file lists and content hashes.
6. Run the repository-established CSV validation command, or a temporary CSV-aware validator when none exists.
7. Use conventional commits on the specification branch, obtain review, and squash-merge into `202607`.

Relevant assumptions: 1, 2, 3, 4, 5, 6, 7, 8.
