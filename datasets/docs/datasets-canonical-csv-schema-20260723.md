## Goals

All 12 top-level prize CSV files MUST use one ordered, lossless 26-column schema:

`award_record_id,year,category,prize,motivation,prize_share,source_laureate_id,laureate_type,full_name,birth_date,birth_year,birth_city,birth_country,birth_coordinates,citizenship_countries,sex,affiliation_name,affiliation_city,affiliation_country,affiliation_coordinates,death_date,death_city,death_country,field_language,biographical_note,remarks`

Success means every input row remains one output row in the same order, every nonempty source value is preserved exactly in its mapped field,
every award record has a unique persistent identifier, canonical fields absent from a source and both coordinate fields are empty CSV fields,
existing literal placeholders remain unchanged, and all 12 datasets use the exact canonical header.

The resulting records SHALL support all 12 awards without cross-file laureate deduplication and SHALL provide stable award identifiers for
later educational concept tags and Wikipedia links.

## Background

The directory currently contains 12 top-level CSV files. `nobel.csv` (lines 1-1027) has the broadest 19-column biographical schema. The other
11 files use compact award schemas; `breakthrough.csv` (lines 1-131) and `crafoord.csv` (lines 1-83) also contain enriched birth and affiliation
fields. The current files have 2,686 parsed data rows in total.

The previous draft mapped every non-Nobel `country` value to `birth_country` and accepted removal of `birth_info`, enriched `birth_year`, and
`remarks`. Repository evidence shows that Crafoord `country` was sourced from Wikidata property P27 (country of citizenship), not birthplace.
It also shows that Breakthrough's collective LIGO record uses `birth_year=2016` for a publication rather than a person. The product decision is
now to distinguish birthplace, source-provided year text, citizenship, and affiliation geography and to preserve every available top-level
source value for later enrichment.

The future explorer will load all 12 canonical datasets as independent award records. It will not initially attempt to identify the same
person across records. Educational links concern concepts associated with an award, such as relativity or the photoelectric effect, rather
than being embedded as Markdown in names or motivation text.

The parent directory is a newly initialized Git worktree. Under the current execution identity, Git commands require the per-command
safe-directory override `-c safe.directory=/home/antb2/dev/rsync/nobel`; implementation MUST NOT change global Git configuration.

## Assumptions

1. **Load-bearing:** Each CSV row is an independent award record; repeated people across rows or files remain separate.
2. **Load-bearing:** Non-Nobel `country` values represent source-stated citizenship or nationality and map to `citizenship_countries`, not birthplace or residence.
3. **Load-bearing:** Existing `rationale` maps to `motivation`, `laureate` maps to `full_name`, and non-Nobel `source` maps to `prize`.
4. **Load-bearing:** `birth_year` remains a distinct lossless source field because at least one collective Breakthrough record does not describe a person's birth.
5. Empty canonical fields are serialized as empty values, not invented values such as `NA`, except where an existing literal value is preserved.
6. Row order, row count, Unicode text, embedded punctuation, and all existing field text remain unchanged.
7. **Load-bearing:** Coordinates are WGS84 decimal-degree pairs ordered as `longitude,latitude`; coordinate enrichment is outside this conversion.
8. **Load-bearing:** Educational concepts are many-to-many with award records and will be stored outside award text in a later step.

## Canonical schema and mapping

Every output MUST use the exact header and order in Goals.

| Existing field | Canonical field | Applies to |
| --- | --- | --- |
| generated persistent value | `award_record_id` | all files |
| `year`, `Year` | `year` | all files |
| `field` | `category` | Breakthrough, Crafoord, Wolf |
| existing `category` | `category` | Nobel, Lasker |
| existing `prize` | `prize` | Nobel |
| existing `source` | `prize` | all non-Nobel awards |
| `rationale` | `motivation` | non-Nobel awards |
| existing `motivation` | `motivation` | Nobel |
| existing `prize_share` | `prize_share` | Nobel |
| existing `laureate_id` | `source_laureate_id` | Nobel |
| existing `laureate_type` | `laureate_type` | Nobel |
| `laureate`, existing `full_name` | `full_name` | all files |
| `birth_year` | `birth_year` | Breakthrough, Crafoord, Fields Medal |
| existing `birth_date`, `birth_city`, `birth_country` | same semantic field | Nobel |
| `country` | `citizenship_countries` | all non-Nobel awards |
| existing `sex` | `sex` | Nobel, Fields Medal |
| `affiliation` | `affiliation_name` | Breakthrough, Crafoord, Fields Medal |
| `organization_name` | `affiliation_name` | Nobel |
| `organization_city` | `affiliation_city` | Nobel |
| `organization_country` | `affiliation_country` | Nobel |
| existing `death_date`, `death_city`, `death_country` | same semantic field | Nobel |
| existing `field_language` | `field_language` | Nobel |
| `birth_info` | `biographical_note` | Breakthrough, Crafoord |
| existing `remarks` | `remarks` | Fields Medal |

No existing source field is discarded. Fields without a mapping for a particular dataset MUST be empty. The conversion MUST NOT derive
`birth_country`, `affiliation_city`, or `affiliation_country` from citizenship or free-form affiliation text.

`full_name`, `motivation`, and `biographical_note` MUST be preserved verbatim, including any existing literal HTML tags or entities, and
treated as untrusted text by consumers. The conversion MUST NOT generate Markdown, HTML, inferred Wikipedia URLs, or automatically
constructed article links.

### Requirement: Lossless canonical mapping — Conversion MUST preserve every source field

#### Scenario: Compare before and after
- WHEN a source row and its converted award record are compared through the mapping table
- THEN every nonempty source value appears unchanged in its canonical destination
- AND no source field is omitted from the mapping
- AND input row order is unchanged

## Award record identity

Each converted row MUST receive an `award_record_id` formed from the lowercase dataset filename stem, a hyphen, and the one-based data-row
position padded to six digits. For example, the first data row in `nobel.csv` is `nobel-000001`.

Identifiers MUST be unique across all 12 files and MUST be written into the canonical datasets as persistent data. Row position defines only
the initial assignment during this conversion. Once assigned, identifiers MUST be treated as stored identity and MUST NOT be regenerated
after reordering or field edits. A later refresh MAY update an existing row in place or append a new record with the next unused identifier;
any full upstream replacement requires an explicit old-to-new reconciliation outside this conversion. Deleted identifiers MUST NOT be reused.

The identifier belongs to the award record, not the person. Two awards for the same person MUST retain separate `award_record_id` values.
`source_laureate_id` preserves Nobel's existing source-specific person identifier but MUST NOT be treated as a cross-dataset identity.

### Requirement: Stable award identity — Every row MUST have one unique award identifier

#### Scenario: Initialize canonical identifiers
- WHEN all converted records are inspected
- THEN every `award_record_id` matches `^[a-z0-9_]+-[0-9]{6}$`
- AND no identifier is empty or duplicated
- AND repeated laureate names remain independent records

## Geography and enrichment fields

The canonical geography fields have distinct meanings:

- `birth_country` is a verified place of birth.
- `citizenship_countries` is the source-stated citizenship or nationality and MAY contain the existing semicolon-separated values.
- `affiliation_city` and `affiliation_country` describe the listed research institution or organization.
- Neither citizenship nor affiliation establishes residence; this schema has no `residence_country` field.

`birth_coordinates` SHALL represent the place of birth and `affiliation_coordinates` SHALL represent the listed affiliation. This conversion
MUST leave both fields empty in every row and MUST NOT geocode or infer coordinates.

When populated by later enrichment, each coordinate field MUST contain either one complete `longitude,latitude` pair or be empty. Both
members MUST be base-10 WGS84 decimal degrees: longitude from -180 through 180 followed by latitude from -90 through 90. CSV-aware
serialization MUST quote a populated pair because its comma belongs to the field value.

### Requirement: Empty coordinate placeholders — Conversion MUST add both coordinate fields without enrichment

#### Scenario: Convert current datasets
- WHEN any top-level CSV row is converted
- THEN `birth_coordinates` is empty
- AND `affiliation_coordinates` is empty

## Educational concepts

The educational goal is to connect an award to explanatory subjects, not to alter its source text or assume the link should be a laureate
biography. A later step SHALL model a controlled concept vocabulary and a many-to-many association keyed by `award_record_id`, allowing
examples such as `relativity` or `photoelectric-effect` to carry labeled Wikipedia URLs.

Creating concept records, assigning tags, and fetching Wikipedia content are outside this conversion. The conversion MUST only establish the
stable award identity required by that later work.

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

CSV-aware parsing and writing MUST be used so quoted commas, embedded quotation marks, Unicode, and line endings remain valid. The
implementation MUST validate headers before conversion and fail visibly on an unexpected header rather than guessing.

The expected input headers are exact contracts:

- `abel_prize.csv`, `japan_prize.csv`, `kyoto_prize.csv`, `max_planck_medal.csv`, `shaw_prize.csv`, and `turing_award.csv`:
  `year,laureate,country,rationale,source`
- `lasker_awards.csv`: `year,category,laureate,country,rationale,source`
- `wolf_prize.csv`: `year,field,laureate,country,rationale,source`
- `breakthrough.csv` and `crafoord.csv`:
  `year,field,laureate,birth_info,birth_year,country,rationale,affiliation,source`
- `fields.csv`: `year,laureate,sex,country,birth_year,remarks,affiliation,source`
- `nobel.csv`:
  `year,category,prize,motivation,prize_share,laureate_id,laureate_type,full_name,birth_date,birth_city,birth_country,sex,organization_name,organization_city,organization_country,death_date,death_city,death_country,field_language`

### Requirement: Canonical shape — Every CSV MUST have the exact ordered 26-column header

#### Scenario: Validate all files
- WHEN all 12 top-level CSV files are parsed after conversion
- THEN each parser field list exactly equals the canonical header
- AND every row has exactly 26 fields

## Compatibility, safety, and reporting

This is a breaking schema change for every CSV consumer. Consumers MUST migrate old names including `laureate`, `country`, `rationale`,
`source`, and Nobel's `laureate_id` and `organization_*` fields to their canonical replacements. The clean schema deliberately does not retain
aliases or duplicate the same source value into compatibility columns.

The implementation SHALL print or retain a concise conversion report per file containing its name, input row count, output row count, mapped
source fields, and assigned identifier range. Reports MUST NOT include row content. A mismatch in header, row count, mapped-value
preservation, identifier uniqueness, or output shape MUST stop conversion and leave the affected original file intact.

No network access is required. CSV values are untrusted data and MUST pass only through CSV parsing and serialization, never be interpreted
as paths, commands, policy, formulas, Markdown, or HTML.

## Verification

Verification MUST include:

1. Parse all 12 top-level CSVs and assert the exact canonical field list and 26 fields per row.
2. Assert unchanged parsed data-row counts: 29 Abel, 130 Breakthrough, 82 Crafoord, 68 Fields, 116 Japan, 129 Kyoto, 423 Lasker,
   90 Max Planck, 1,026 Nobel, 121 Shaw, 81 Turing, and 391 Wolf.
3. Compare every nonempty input field to its mapped output destination and assert exact text equality and unchanged row order.
4. Assert every source header field has exactly one documented canonical destination.
5. Assert 2,686 nonempty, unique, correctly formatted `award_record_id` values and the expected first and last identifiers per file.
6. Assert `birth_coordinates` and `affiliation_coordinates` are empty in every converted row.
7. Assert every existing `birth_year` maps only to `birth_year`, non-Nobel `country` values populate only `citizenship_countries`, and existing Nobel birthplace and affiliation geography retain their distinct mappings.
8. Run the repository-established CSV validation command if one is discovered; otherwise use a temporary CSV-aware validation helper and report its exact checks.

## Scope

Expected implementation scope is 12 existing CSV files. Estimated implementation change size is 2,686 CSV data-row rewrites and no
maintained Python changes. A temporary, reviewable conversion helper MAY be used from a temporary directory and removed after verification;
a maintained project script requires an explicit request. Concept/tag CSVs, Wikipedia URLs, application code, deduplication, geocoding, and
SQLite are outside this step.

Implementation SHALL use one branch for this specification, conventional commits, review before merge, and a squash merge into the `202607`
month branch. Unit-level schema, mapping, and identity checks SHALL be created alongside implementation where the repository provides a test
location.
