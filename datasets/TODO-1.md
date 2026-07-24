# Dataset completeness TODO 1

Snapshot: 2026-07-24 (refreshed — counts recomputed from current files).

Each count is the number of blank cells among the file's data rows. A blank is not automatically an error: verify the value against an authoritative source, fill it only when it applies, and otherwise leave it blank. Keep one row per laureate or recipient. Use today's place, country, and location names.

Some recent enrichment (lasker, breakthrough) was filled from model knowledge and is not yet source-verified — treat those bio values as provisional until cross-checked. Prize source urls are listed in `AGENTS.md`.

All files currently have `award_record_id`, `year`, `prize`, and `full_name` on every row. For every file:

- verify that every expected recipient and award year is present;
- complete applicable award, recipient, birthplace, affiliation, and death-place fields from authoritative sources;
- add `birth_coordinates` and `affiliation_coordinates` only after the named places are verified;
- do not infer `prize_share`, death details for living recipients, or other inapplicable values; and
- preserve the 26-column header and existing record IDs.

## 1. `abel_prize.csv` — 29 rows

- Entirely blank: `category`, `prize_share`, `source_laureate_id`, `laureate_type`, `birth_coordinates`, `affiliation_coordinates`, `field_language`, `biographical_note`, `remarks`.
- Partly blank: `death_date` 22, `death_city` 22, `death_country` 22.
- Status: birthplace, birth date, sex, and affiliation complete. Remaining death gaps are the 22 living laureates (verify before filling).
- TODO: verify whether the non-applicable category and share fields should remain blank; add source IDs, recipient type, verified coordinates, and any applicable death details.

## 2. `breakthrough.csv` — 148 rows

- Entirely blank: `prize_share`, `source_laureate_id`, `birth_coordinates`, `affiliation_city`, `affiliation_country`, `affiliation_coordinates`, `field_language`, `remarks`.
- Partly blank: `birth_date` 4, `birth_year` 4, `birth_city` 14, `birth_country` 14, `citizenship_countries` 7, `sex` 14, `affiliation_name` 13, `death_date` 132, `death_city` 144, `death_country` 144, `biographical_note` 68.
- Status: lumped rows split into one record per person (130 → 148, new ids `000131`–`000148`); 4 named collaborations set to `laureate_type` = Organization; `laureate_type` now complete. Birth, citizenship, and sex enriched from model knowledge (provisional); the remaining birth/sex blanks are the 4 organization rows. 16 deaths recorded.
- Note: bio was filled from model knowledge, not source-verified — spot errors exist (e.g. Rainer Weiss birthplace, Joseph Polchinski missing death).
- TODO: source-verify the provisional bio; split `affiliation_name` into `affiliation_city`/`affiliation_country`; add source IDs, verified coordinates, and applicable death details.

## 3. `crafoord.csv` — 82 rows

- Entirely blank: `prize_share`, `source_laureate_id`, `laureate_type`, `birth_date`, `birth_city`, `birth_country`, `birth_coordinates`, `sex`, `affiliation_name`, `affiliation_city`, `affiliation_country`, `affiliation_coordinates`, `death_date`, `death_city`, `death_country`, `field_language`, `remarks`.
- Partly blank: `birth_year` 1, `citizenship_countries` 1, `biographical_note` 1.
- Note: enrichment agents crashed mid-run; all person-level fields are effectively empty. Needs a full re-run.
- TODO: full recipient enrichment — birth details, sex, affiliations, applicable death details, source IDs/types, and verified coordinates.

## 4. `fields.csv` — 68 rows

- Entirely blank: `category`, `motivation`, `prize_share`, `source_laureate_id`, `laureate_type`, `birth_coordinates`, `affiliation_city`, `affiliation_country`, `affiliation_coordinates`, `field_language`, `biographical_note`.
- Partly blank: `birth_date` 5, `birth_city` 5, `birth_country` 1, `death_date` 47, `death_city` 49, `death_country` 47, `remarks` 67.
- Status: birthplace, birth date, sex, affiliation, and all deceased laureates' death data complete. Remaining `birth_date`/`birth_city` gaps are the four 2026 laureates plus Birkar (exact dates unverified); remaining death gaps are living laureates.
- Note: `affiliation_name` embeds the country (e.g. `"University of Chicago, USA"`) while `affiliation_city`/`affiliation_country` sit empty — restructure into separate place columns.
- TODO: add official citations when available; split affiliation places; verify the 2026 roster and its birth dates; add source IDs/types and verified coordinates.

## 5. `japan_prize.csv` — 116 rows

- Entirely blank: `category`, `prize_share`, `source_laureate_id`, `laureate_type`, `birth_coordinates`, `affiliation_coordinates`, `death_date`, `death_city`, `death_country`, `field_language`, `biographical_note`, `remarks`.
- Partly blank: `birth_date` 1, `birth_city` 20, `birth_country` 15, `sex` 2, `affiliation_city` 1.
- Status: birth date, sex, and affiliation largely complete; death data not yet started (0/116).
- TODO: complete the bounded birth, sex, and affiliation-city gaps; add applicable death details, source IDs/types, and verified coordinates. Determine whether award fields now embedded in `motivation` belong in `category`.

## 6. `kyoto_prize.csv` — 129 rows

- Entirely blank: `prize_share`, `source_laureate_id`, `laureate_type`, `birth_coordinates`, `affiliation_coordinates`, `field_language`, `biographical_note`, `remarks`.
- Partly blank: `birth_date` 14, `birth_year` 4, `birth_city` 17, `birth_country` 1, `affiliation_name` 33, `affiliation_city` 34, `affiliation_country` 34, `death_date` 69, `death_city` 76, `death_country` 75.
- Status: official category separated from `motivation` and person fields enriched since the last snapshot; birth data largely complete; ~33 affiliation gaps; death data partial.
- TODO: fill remaining birth and affiliation gaps; complete applicable death details; add source IDs/types and verified coordinates.

## 7. `lasker_awards.csv` — 423 rows

- Entirely blank: `prize_share`, `source_laureate_id`, `birth_coordinates`, `affiliation_name`, `affiliation_city`, `affiliation_country`, `affiliation_coordinates`, `field_language`, `biographical_note`, `remarks`.
- Partly blank: `birth_date` 11, `birth_year` 17, `birth_city` 43, `birth_country` 10, `sex` 11, `death_date` 166, `death_city` 172, `death_country` 171.
- Status: `laureate_type` complete (415 Individual / 8 Organization); birth details, sex, and death data enriched from model knowledge (provisional); citizenship already complete. Affiliation entirely blank.
- Note: bio unvalidated — spot errors exist (e.g. Michael Heidelberger death year).
- TODO: source-verify the provisional bio; add affiliations; source IDs/types; verified coordinates; leave prize share blank unless explicitly stated by the award source.

## 8. `max_planck_medal.csv` — 90 rows

- Entirely blank: `category`, `prize_share`, `source_laureate_id`, `laureate_type`, `birth_coordinates`, `affiliation_coordinates`, `field_language`, `biographical_note`, `remarks`.
- Partly blank: `motivation` 64, `birth_date` 19, `birth_year` 2, `birth_city` 21, `birth_country` 2, `affiliation_name` 16, `affiliation_city` 16, `affiliation_country` 16, `death_date` 30, `death_city` 31, `death_country` 31.
- Status: person fields enriched since the last snapshot; 64 official citations still missing.
- TODO: add the 64 missing citations; complete the birth and affiliation gaps; add source IDs/types, applicable death details, and verified coordinates. Confirm that category and prize share are not applicable.

## 9. `nobel.csv` — 1,026 rows

- Entirely blank: `birth_coordinates`, `citizenship_countries`, `affiliation_coordinates`, `biographical_note`, `remarks`.
- Partly blank: `motivation` 88, `birth_date` 50, `birth_year` 1,009, `birth_city` 40, `birth_country` 34, `sex` 31, `affiliation_name` 268, `affiliation_city` 269, `affiliation_country` 269, `death_date` 428, `death_city` 445, `death_country` 439, `field_language` 400.
- TODO: distinguish organizations from people before enrichment; add citizenship and verified coordinates; complete missing motivations and applicable person, affiliation, death-place, and field/language data. Treat `birth_year` as optional when a complete `birth_date` already supplies the year.

## 10. `shaw_prize.csv` — 121 rows

- Entirely blank: `category`, `prize_share`, `birth_coordinates`, `affiliation_coordinates`, `death_city`, `death_country`, `field_language`, `biographical_note`, `remarks`.
- Partly blank: `source_laureate_id` 87, `laureate_type` 86, `birth_date` 85, `birth_year` 91, `birth_city` 59, `birth_country` 53, `sex` 86, `affiliation_name` 77, `affiliation_city` 113, `affiliation_country` 77, `death_date` 119.
- TODO: complete source IDs/types and recipient details, structure the official category currently embedded in `motivation`, fill affiliations and applicable death details, and add verified coordinates.

## 11. `turing_award.csv` — 81 rows

- Entirely blank: `category`, `prize_share`, `source_laureate_id`, `laureate_type`, `birth_coordinates`, `affiliation_coordinates`, `field_language`, `biographical_note`, `remarks`.
- Partly blank: `birth_city` 3, `affiliation_city` 14, `death_date` 48, `death_city` 50, `death_country` 48.
- Status: birth date, sex, birth country, and affiliation largely complete; 33 deaths recorded.
- TODO: complete the bounded birthplace and affiliation-city gaps; add source IDs/types, applicable death details, and verified coordinates. Confirm that category and prize share are not applicable.

## 12. `wolf_prize.csv` — 391 rows

- Entirely blank: `prize_share`, `source_laureate_id`, `birth_coordinates`, `affiliation_coordinates`, `field_language`, `biographical_note`, `remarks`.
- Partly blank: `birth_date` 264, `birth_year` 258, `birth_city` 265, `birth_country` 192, `affiliation_name` 269, `affiliation_city` 269, `affiliation_country` 269, `death_date` 324, `death_city` 327, `death_country` 327.
- Status: `laureate_type` complete; Mathematics and Physics recipients enriched. Remaining gaps are Chemistry, Medicine, Agriculture, and Arts (~251 records).
- TODO: complete the remaining categories and affiliation gaps, set source IDs/types, add applicable death details and verified coordinates, and preserve meaningful `YYYY/YYYY` award-year labels.
