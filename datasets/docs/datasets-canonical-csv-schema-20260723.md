## Goals

All prize CSV files MUST use one ordered 20-column header based on `nobel.csv`, with `source` appended for provenance:

`year,category,prize,motivation,prize_share,laureate_id,laureate_type,full_name,birth_date,birth_city,birth_country,sex,organization_name,organization_city,organization_country,death_date,death_city,death_country,field_language,source`

Success means every existing data row remains one row, every mapped value is carried into its canonical column without rewriting its text, every unmapped nonempty value is explicitly counted before accepted loss, unavailable values are empty CSV fields, and all 12 top-level CSV datasets use the canonical shape.

## Background

The directory currently contains 12 top-level CSV files. `nobel.csv` (lines 1-1027) has the broadest 19-column biographical schema but no source-label column. Nine award files use compact variants of the `year`/laureate/country/rationale/source schema, while `breakthrough.csv` (lines 1-131) and `crafoord.csv` (lines 1-83) also contain enriched birth and affiliation fields. No top-level generator remains: the older Nobel dataset, three component Breakthrough datasets, `merge_breakthrough.py`, and `build_crafoord.py` are under `trash/` and are outside this conversion.

The current enriched-data baselines are 80 nonempty `birth_info` and 79 nonempty `birth_year` values in `breakthrough.csv`, plus 81 nonempty values in each field in `crafoord.csv`. These values have no destination under the requested mapping and their counted removal is accepted. `fields.csv` has a separate contracted mapping from all 68 nonempty `birth_year` values to `birth_date`; its one nonempty `remarks` value is accepted loss after reporting.

This directory is not inside a Git worktree, so branch, commit, and merge workflow requirements cannot be executed here unless the files are first placed in a repository.

## Assumptions

1. **Load-bearing:** The canonical schema is the ordered 19-column `nobel.csv` header followed by `source`.
2. **Load-bearing:** Existing `country` values map to `birth_country`, preserving their text even though some source datasets describe nationality rather than literal birthplace.
3. **Load-bearing:** Existing `rationale` values map to `motivation`, and `laureate` maps to `full_name`.
4. Empty canonical fields are serialized as empty values, not invented values such as `NA`, except that existing literal values are preserved.
5. Row order, row count, Unicode text, embedded punctuation, and existing field text remain unchanged.
6. **Load-bearing:** Files under `trash/` are not active datasets or implementation inputs; top-level `breakthrough.csv` and `crafoord.csv` are authoritative static inputs.
7. Existing `source` values are award/source labels rather than URLs or citations; this change preserves those labels but does not claim to add external provenance links.

## Canonical field mapping

Every output MUST use the exact header and order in Goals.

| Existing field | Canonical field | Applies to |
| --- | --- | --- |
| `year`, `Year` | `year` | all files |
| `field` | `category` | Breakthrough, Crafoord, Wolf |
| existing `category` | `category` | Lasker |
| existing `source` | `prize` | all non-Nobel awards |
| `rationale` | `motivation` | non-Nobel awards |
| `laureate` | `full_name` | non-Nobel awards |
| `birth_year` | `birth_date` | Fields Medal only |
| `country` | `birth_country` | non-Nobel awards |
| existing `sex` | `sex` | Fields Medal |
| `affiliation` | `organization_name` | Breakthrough, Crafoord, Fields Medal |
| existing `source` | `source` | non-Nobel awards |

For non-Nobel awards, the existing `source` value MUST populate both `prize` and `source`: `prize` identifies the award while `source` preserves the existing award/source label for compatibility. Fields without a mapping MUST be left empty. Existing canonical Nobel fields MUST remain unchanged, with only an empty `source` appended because no source value currently exists.

`birth_info` and `birth_year` in `breakthrough.csv` and `crafoord.csv`, plus `remarks` in `fields.csv`, have no canonical destination and MUST NOT be substituted into a semantically different field. Their values MAY be dropped only after verification reports the nonempty count for every affected field in every file. This exception does not apply to `fields.csv` `birth_year`, which MUST map to `birth_date`.

### Requirement: Canonical header — Every CSV MUST have the exact ordered 20-column header

#### Scenario: Validate all files
- WHEN all 12 top-level CSV files are parsed after conversion
- THEN each parser field list exactly equals the canonical header
- AND every row has exactly 20 fields

### Requirement: Preserve records — Conversion MUST preserve record identity and content

#### Scenario: Compare before and after
- WHEN a source and converted file are compared through its mapping
- THEN the data-row count is unchanged
- AND each nonempty mapped source value appears unchanged in its destination field
- AND input row order is unchanged

### Requirement: Accounted field loss — Every nonempty unmapped value MUST be counted before removal

#### Scenario: Convert enriched and Fields datasets
- WHEN `breakthrough.csv`, `crafoord.csv`, and `fields.csv` are converted
- THEN the conversion report identifies each unmapped field and its nonempty input count
- AND the report matches the current baselines of 80/79 for Breakthrough `birth_info`/`birth_year`, 81/81 for Crafoord `birth_info`/`birth_year`, and 1 for Fields `remarks`
- AND none of those unmapped values is silently placed in a canonical field

## Static dataset conversion

The following complete files SHALL be rewritten to the canonical header and mapped rows:

- `abel_prize.csv` lines 1-30
- `breakthrough.csv` lines 1-131
- `crafoord.csv` lines 1-83
- `fields.csv` lines 1-69
- `japan_prize.csv` lines 1-117
- `kyoto_prize.csv` lines 1-130
- `lasker_awards.csv` lines 1-424
- `max_planck_medal.csv` lines 1-91
- `nobel.csv` lines 1-1027
- `shaw_prize.csv` lines 1-122
- `turing_award.csv` lines 1-82
- `wolf_prize.csv` lines 1-392

CSV-aware parsing and writing MUST be used so quoted commas, embedded quotation marks, Unicode, and line endings remain valid. The implementation MUST validate headers before conversion and fail visibly on an unexpected header rather than guessing.

Files under `trash/` MUST remain unchanged. The implementation MUST NOT regenerate `breakthrough.csv` or `crafoord.csv`; both SHALL be converted directly from their current top-level contents.

## Compatibility and data quality

This is a breaking schema change for consumers of every CSV except the first 19 columns of `nobel.csv`. Consumers using old names such as `laureate`, `rationale`, `country`, or `affiliation` MUST migrate to the canonical names.

The implementation SHALL print or otherwise retain a concise conversion report per file containing file name, input row count, output row count, and count of nonempty unmapped values. Reports MUST NOT include row content. A mismatch in header, row count, or mapped-value preservation MUST stop conversion and leave the affected original file intact.

No network access is required. CSV values are untrusted data and MUST be passed only through CSV parsing and serialization, never interpreted as paths, commands, policy, or formulas.

## Verification

Verification MUST include:

1. Parse all 12 top-level CSVs and assert the exact canonical field list and 20 fields per row.
2. Assert unchanged parsed data-row counts: 29 Abel, 130 Breakthrough, 82 Crafoord, 68 Fields, 116 Japan, 129 Kyoto, 423 Lasker, 90 Max Planck, 1026 Nobel, 121 Shaw, 81 Turing, and 391 Wolf.
3. Compare every mapped nonempty input value to its output destination and assert unchanged row order.
4. Report per-file nonempty values dropped from every unmapped field and assert the documented `birth_info`, enriched `birth_year`, and `remarks` baselines.
5. Assert no file under `trash/` changed and no generator was invoked.
6. Run the repository-established CSV validation command if one is discovered; otherwise use a temporary CSV-aware validation helper and report its exact checks.

## Scope

Expected implementation scope is 12 existing CSV files. Estimated implementation change size is 2,686 CSV data-row rewrites and no Python changes. A temporary, reviewable conversion helper MAY be used from a temporary directory and removed after verification; a maintained project script requires an explicit request.

When Git becomes available, implementation SHALL use one branch for this specification, conventional commits, review before merge, and a squash merge into the `202607` month branch. Unit-level schema and mapping checks SHALL be created alongside implementation where the repository provides a test location.
