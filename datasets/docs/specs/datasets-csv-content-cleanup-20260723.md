## Goals

The 12 canonical prize CSVs MUST be free of verified source-serialization and missing-value artifacts while preserving their 26-column schema,
2,686 award records, stable identifiers, row order, historical labels, and meaningful source text.

Success means:

- exact missing-value placeholders are canonical empty fields;
- values have no leading or trailing whitespace;
- HTML italic tags and character entities are represented as plain Unicode text;
- presentation-only quote pairs no longer wrap complete motivation values;
- complete dates are valid ISO calendar dates, while known year-only dates use `birth_year`;
- the collective LIGO record does not claim a personal birth year; and
- every change is covered by a baseline-to-output assertion.

## Background

The canonical schema conversion is complete on all 12 active CSVs. A CSV-aware audit found no missing required identifiers, years, prize names,
or laureate names; no duplicate records; no malformed country lists; no control characters; no embedded newlines; and 2,686 unique
`award_record_id` values.

Three files contain bounded cleanup work:

- `breakthrough.csv` lines 37-41, 51-52, 61, 69-70, 77, 87-88, 94, 101, 109, 115, 120, and 130 contain 18 motivations wrapped in
  presentation-only quote pairs, plus one collective LIGO record whose `birth_year=2016` describes the publication named in its
  `biographical_note`.
- `nobel.csv` lines 2-1027 contain 938 motivations wrapped in presentation-only quote pairs, 2,344 exact `NA` placeholders, 400 exact
  `No Data` placeholders, 20 `<i>`/`</i>` tags, 12 HTML character entities, two names with edge whitespace, and 17 year-only birth dates
  serialized as `YYYY-00-00`.
- `turing_award.csv` lines 4-5, 13-16, 23-24, 27, 29-30, 32-34, 37-38, 42-44, 52, 56-57, 62, 77, and 79-80 contain 26 motivations with one
  trailing whitespace character.

The non-simple award years in Breakthrough (`YYYY (special)`) and Wolf (`YYYY/YYYY`) are meaningful award labels, not defects. Historical
country labels and ordered semicolon-separated citizenship lists are also meaningful source data. Missing optional values are expected and
MUST remain empty rather than being enriched or guessed.

## Assumptions

1. **Load-bearing:** Exact values `NA` and `No Data` mean unavailable data and normalize to an empty CSV field.
2. **Load-bearing:** A double-quote pair wrapping an entire nonempty motivation is presentation syntax, not part of the award citation.
3. **Load-bearing:** Only literal `<i>` and `</i>` tags are removable markup; their enclosed text remains unchanged.
4. HTML character entities decode to their Unicode characters, followed by NFC normalization.
5. **Load-bearing:** Nobel `YYYY-00-00` birth dates preserve their year in `birth_year` and leave `birth_date` empty.
6. **Load-bearing:** Breakthrough record `breakthrough-000051` is a collective publication record; its `birth_year` becomes empty because its full publication date remains in `biographical_note`.
7. Valid special/range award years, historical geography, country-list ordering, internal whitespace, punctuation, and capitalization remain unchanged.
8. No network lookup, geocoding, educational tagging, source recovery, laureate deduplication, or missing-data enrichment belongs to this cleanup.

## Deterministic normalization

Each field value SHALL pass through one obvious normalization path:

1. Remove leading and trailing Unicode whitespace.
2. Replace an exact `NA` or `No Data` value with an empty value.
3. Remove literal case-insensitive `<i>` and `</i>` tags and decode HTML character entities.
4. Normalize decoded text to Unicode NFC.
5. For `motivation` only, remove exactly one leading and trailing ASCII double quote when both wrap the complete value, then trim newly exposed
   edge whitespace.

The normalizer MUST NOT collapse internal whitespace, alter punctuation or capitalization, rewrite country names, split collective names,
change award-year labels, sanitize arbitrary angle-bracket text, or infer missing values.

### Requirement: Canonical missing values — Exact source placeholders MUST become empty fields

#### Scenario: Normalize Nobel placeholders
- WHEN the 2,344 `NA` cells and 400 `No Data` cells are processed
- THEN every affected canonical value is empty
- AND no non-exact substring or other value is removed

### Requirement: Plain educational text — Source presentation markup MUST become readable Unicode

#### Scenario: Normalize motivations and entity-encoded values
- WHEN the verified wrapper quotes, italic tags, and character entities are processed
- THEN wrapper syntax and verified markup tokens are absent
- AND enclosed text and decoded Unicode characters remain in the same record and field

### Requirement: Semantic dates — Partial or non-person dates MUST NOT masquerade as complete birth dates

#### Scenario: Normalize partial Nobel birth dates
- WHEN a `birth_date` matches `^([0-9]{4})-00-00$`
- THEN `birth_date` is empty
- AND the captured year is stored unchanged in the previously empty `birth_year`

#### Scenario: Normalize the LIGO collective
- WHEN `breakthrough-000051` is processed
- THEN `birth_year` is empty
- AND `biographical_note` remains unchanged

## Affected datasets

Only these files SHALL change:

- `breakthrough.csv` lines 37-41, 51-52, 61, 69-70, 77, 87-88, 94, 101, 109, 115, 120, and 130
- `nobel.csv` lines 2-1027
- `turing_award.csv` lines 4-5, 13-16, 23-24, 27, 29-30, 32-34, 37-38, 42-44, 52, 56-57, 62, 77, and 79-80

The remaining nine CSV files MUST retain byte-identical contents. All 12 files MUST retain the exact ordered canonical header.

Each affected file MUST be written through CSV-aware serialization to a temporary file, parsed and verified, and only then replace its
original. A failed precondition or verification MUST leave the original file intact. The implementation SHALL emit a concise report of file,
row count, and correction counts without printing source text.

## Compatibility and safety

This is a value-normalization change, not a schema change. Consumers that treated literal placeholder strings, wrapper quote characters, HTML
syntax, or zero month/day components as meaningful will observe cleaned values. Record IDs, field names, field order, record count, and record
order remain compatible.

CSV fields are untrusted data. Cleanup MUST treat them only as values, never as commands, paths, formulas, HTML to render, policy, or identity.
The implementation MUST NOT fetch or infer replacement content.

## Verification

Verification MUST prove:

1. All 12 files retain the exact ordered 26-column header.
2. Per-file and total row counts remain unchanged at 2,686 records.
3. All 2,686 `award_record_id` values retain their original record and order and remain unique.
4. Every source-to-output difference matches one of the deterministic normalization rules or the two explicit date rules.
5. Exact `NA` and `No Data` values, edge whitespace, verified HTML tags/entities, and complete-value motivation quote wrappers have zero
   remaining occurrences.
6. Every nonempty `birth_date` is a valid ISO calendar date and every nonempty `birth_year` is four digits.
7. The 17 Nobel partial dates retain their year in `birth_year`, and `breakthrough-000051` has an empty `birth_year` with unchanged
   `biographical_note`.
8. Special/range award years, country values, country-list ordering, record names apart from edge trimming, and all other untouched values
   equal the baseline.
9. The nine unaffected CSV files are byte-identical to their baseline.
10. The existing deep audit and a temporary independent CSV-aware verifier both pass for the corrected surface.

## Scope

Expected implementation scope is three existing CSV files and approximately 3,750 normalized cells, dominated by Nobel wrapper quotes and
missing-value placeholders. No maintained Python, application, concept/tag, or schema changes are required.

Implementation SHALL remain on the existing specification branch, use a conventional commit, undergo review before merge, and be
squash-merged into the `202607` month branch. A temporary validator MAY be used outside the worktree and removed after verification.
