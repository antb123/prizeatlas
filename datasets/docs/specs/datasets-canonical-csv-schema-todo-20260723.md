## Implementation tasks

### ID: CSV-00 — Capture immutable conversion baselines

Depends-on: none

Files: all 12 top-level CSV files listed in the specification.

Steps → verify:

1. Using the documented safe-directory override, create and switch to the specification's implementation branch before changing any dataset.
2. Create a temporary, outside-the-worktree baseline containing each active CSV's exact header, parsed row count, row order, and every source field value.
3. Assert every active input header and row count matches the exact contracts in the specification before permitting conversion to start.
4. Report the temporary baseline location for CSV-01 through CSV-04; do not modify any dataset.

Relevant assumptions: 1, 2, 3, 4, 5, 6, 7, 8.

### ID: CSV-01 — Normalize standalone compact award datasets

Depends-on: CSV-00

Files: `abel_prize.csv` lines 1-30; `japan_prize.csv` lines 1-117; `kyoto_prize.csv` lines 1-130;
`lasker_awards.csv` lines 1-424; `max_planck_medal.csv` lines 1-91; `shaw_prize.csv` lines 1-122;
`turing_award.csv` lines 1-82; `wolf_prize.csv` lines 1-392.

Steps → verify:

1. Load the CSV-00 baseline for each owned file and stop visibly if any current input differs.
2. Assign each row its persistent `<dataset-stem>-<six-digit-row-position>` `award_record_id`.
3. Map `year → year`, `source → prize`, `rationale → motivation`, `laureate → full_name`, and `country → citizenship_countries`;
   additionally map Lasker `category → category` and Wolf `field → category`.
4. Leave unavailable canonical fields, including both coordinate fields, empty and retain every source value exactly once.
5. Emit the required per-file conversion report, then parse each output and assert the exact canonical header, 26 fields per row,
   unchanged row count/order, equality of every source value at its destination, and unique correctly formatted identifiers.

Relevant assumptions: 1, 2, 3, 5, 6, 7.

### ID: CSV-02 — Normalize enriched Breakthrough and Crafoord datasets

Depends-on: CSV-00

Files: `breakthrough.csv` lines 1-131; `crafoord.csv` lines 1-83.

Steps → verify:

1. Load the CSV-00 baselines and stop visibly if either current input differs.
2. Assign each row its persistent `<dataset-stem>-<six-digit-row-position>` `award_record_id`.
3. Map both static datasets using the specification table, including `birth_info → biographical_note`, `birth_year → birth_year`,
   `country → citizenship_countries`, and `affiliation → affiliation_name`, without invoking or restoring a generator.
4. Leave birthplace, affiliation city/country, and both coordinate fields empty when the source has no explicit values.
5. Assert exact canonical headers, 26 fields per row, 130 Breakthrough rows, 82 Crafoord rows, unchanged order, equality of every
   source value at its destination, and unique identifiers.

Relevant assumptions: 1, 2, 3, 4, 5, 6, 7.

### ID: CSV-03 — Normalize Fields and Nobel datasets

Depends-on: CSV-00

Files: `fields.csv` lines 1-69; `nobel.csv` lines 1-1027.

Steps → verify:

1. Load the CSV-00 baselines and stop visibly if either current input differs.
2. Assign each row its persistent `<dataset-stem>-<six-digit-row-position>` `award_record_id`.
3. Convert Fields using the specification mappings, including `birth_year → birth_year`, `country → citizenship_countries`,
   `affiliation → affiliation_name`, and `remarks → remarks`.
4. Convert Nobel's `laureate_id → source_laureate_id` and `organization_name/city/country → affiliation_name/city/country`;
   preserve its existing birthplace, death, prize, category, motivation, share, type, sex, and field/language values.
5. Leave unavailable canonical fields and both coordinate fields empty.
6. Emit the required reports and assert exact canonical headers, 26 fields per row, 68 Fields rows, 1,026 Nobel rows, unchanged order,
   equality of every source value at its destination, and unique correctly formatted identifiers.

Relevant assumptions: 1, 2, 3, 4, 5, 6, 7.

### ID: CSV-04 — Run cross-dataset acceptance checks

Depends-on: CSV-01, CSV-02, CSV-03

Files: all 12 top-level CSV files listed in the specification.

Steps → verify:

1. Parse all CSVs and assert the exact ordered canonical header and 26 fields in every row.
2. Assert every expected row count and the total of 2,686 records.
3. Compare the CSV-00 baseline to all outputs and confirm every source field value is preserved exactly once through its documented mapping,
   with unchanged row order and no silent data loss.
4. Assert all `award_record_id` values are nonempty, unique, correctly formatted, and use the expected dataset prefix and initial row position.
5. Assert non-Nobel country values appear in `citizenship_countries`, Nobel geography retains its distinct meanings, and both coordinate fields
   are empty in every row.
6. Confirm names, motivations, and biographical notes preserve existing text and markup verbatim without generated Markdown, HTML, or Wikipedia links.
7. Run the repository-established CSV validation command, or a temporary CSV-aware validator when none exists.
8. Use conventional commits on the specification branch, obtain review, and squash-merge into `202607`.

Relevant assumptions: 1, 2, 3, 4, 5, 6, 7, 8.
