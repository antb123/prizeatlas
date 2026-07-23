## Implementation tasks

### ID: CSV-01 — Normalize standalone compact award datasets

Depends-on: none

Files: `abel_prize.csv` lines 1-30; `japan_prize.csv` lines 1-117; `kyoto_prize.csv` lines 1-130; `lasker_awards.csv` lines 1-424; `max_planck_medal.csv` lines 1-91; `shaw_prize.csv` lines 1-122; `turing_award.csv` lines 1-82; `wolf_prize.csv` lines 1-392.

Steps → verify:

1. Capture each current header, row count, row order, and all mapped field values.
2. Convert each row using `year → year`, `source → prize`, `rationale → motivation`, `laureate → full_name`, `country → birth_country`, and `source → source`.
3. Leave all unavailable canonical fields empty and retain field text exactly.
4. Parse each output and assert the exact canonical header, 20 fields per row, unchanged row count/order, and equality of every mapped nonempty value.

Relevant assumptions: 1, 2, 3, 4, 5, 6, 7.

### ID: CSV-02 — Normalize enriched Breakthrough and Crafoord datasets

Depends-on: none

Files: `breakthrough.csv` lines 1-131; `crafoord.csv` lines 1-83.

Steps → verify:

1. Capture both current headers, parsed row counts, row order, mapped values, and nonempty counts for `birth_info` and `birth_year`.
2. Before writing, assert the captured counts are 80/79 for Breakthrough and 81/81 for Crafoord; stop visibly if they differ.
3. Convert both static datasets using the specification table without invoking or restoring a generator.
4. Drop `birth_info` and `birth_year` only after retaining their per-file counts in the conversion report.
5. Assert exact canonical headers, 20 fields per row, 130 Breakthrough rows, 82 Crafoord rows, unchanged order, equality of mapped values, and no change under `trash/`.

Relevant assumptions: 1, 2, 3, 4, 5, 6, 7.

### ID: CSV-03 — Normalize Fields and Nobel datasets

Depends-on: none

Files: `fields.csv` lines 1-69; `nobel.csv` lines 1-1027.

Steps → verify:

1. Capture current headers, parsed row counts, row order, mapped values, and the nonempty `remarks` count.
2. Convert Fields rows using `laureate → full_name`, `sex → sex`, `country → birth_country`, `birth_year → birth_date`, `affiliation → organization_name`, and the shared mappings; report and then drop `remarks`.
3. Preserve all existing `nobel.csv` values and append an empty `source` field.
4. Assert exact canonical headers, 20 fields per row, 68 Fields rows, 1026 Nobel rows, unchanged order, equality of mapped values, and the expected single nonempty dropped `remarks` value.

Relevant assumptions: 1, 2, 3, 4, 5, 6, 7.

### ID: CSV-04 — Run cross-dataset acceptance checks

Depends-on: CSV-01, CSV-02, CSV-03

Files: all 12 top-level CSV files listed in the specification.

Steps → verify:

1. Parse all CSVs and assert the exact ordered canonical header and 20 fields in every row.
2. Assert each expected row count from the specification.
3. Review per-file conversion summaries for every unmapped input field and confirm row-count and mapped-value preservation with no silent unmapped-data loss.
4. Assert no file under `trash/` changed and no generator was invoked.
5. Run the repository-established CSV validation command, or a temporary CSV-aware validator when none exists.
6. If Git becomes available, create one branch for the specification, use conventional commits, obtain review, and squash-merge into `202607`; otherwise explicitly report that version-control checks were not possible.

Relevant assumptions: 1, 2, 3, 4, 5, 6, 7.
