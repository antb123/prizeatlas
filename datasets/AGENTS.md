one row per laureate/recipient
places - use todays name, country, location

## validation rules

- one person per row. if `full_name` lists several people or a collaboration, split into
  one record per named person; a genuine collaboration/team/institution is a single row
  with `laureate_type` = Organization and no personal bio.
- `laureate_type` is `Individual` or `Organization` only.
- preserve the 26-column header and every existing `award_record_id`. new split rows get
  fresh ids; never renumber existing ones.
- fill blank cells only — never overwrite an existing curated value.
- leave a cell blank when unsure. do not guess or infer.
- dates are ISO `YYYY-MM-DD` (or `YYYY` when only the year is known). no other format.
- `birth_city` is the city alone; the country belongs in `birth_country`. no "City, State".
- places use today's names (city, country).
- if a person has died, `death_date` (and place, if known) must be filled; blank death for
  the living. cross-check the "(YYYY–YYYY)" hint in `biographical_note` when present.
- `birth_year` is optional when a complete `birth_date` already supplies it.
- add `birth_coordinates` / `affiliation_coordinates` only after the named place is verified.
- do not infer `prize_share` or death details for the living.
- Organizations carry no birth/sex/death data.

## current data target

- Data verification/retrieval agents write to `awards.sqlite3`, table `awards`, by exact
  `award_record_id`. The CSV files are read-only source snapshots during enrichment.
- The SQLite table preserves all 26 CSV columns and adds `prize_name`,
  `award_wikidata_qid`, and `laureate_wikidata_qid`.
- Finish research before opening a write transaction. Keep transactions short and update
  blank cells only; guard each update against the cell's current blank value.
- `uv run scripts/import_sqlite.py` atomically replaces `awards.sqlite3` from the CSV
  snapshots. Do not run it after SQLite enrichment begins unless a maintainer explicitly
  authorizes discarding or exporting the SQLite-only changes first.
- Verify database health after writes:

  `sqlite3 awards.sqlite3 "PRAGMA integrity_check;"`

  The required result is exactly `ok`.

## local lookup and enrichment tools

Run these commands from this `datasets/` directory.

### `scripts/lookup_coordinates.py`

Read-only lookup for one city or institution. It resolves an exact English Wikipedia title
to its Wikidata item, or accepts a verified Wikidata QID directly:

`uv run scripts/lookup_coordinates.py "University of Cambridge"`

`uv run scripts/lookup_coordinates.py Q35794`

- The command prints one GeoJSON feature and does not modify a CSV or the database.
- `properties.wikidata_id` is the matched place QID.
- `properties.dataset_coordinates` is ready for the dataset and is always
  `longitude,latitude`, rounded to four decimal places.
- `properties.source` is the Wikidata URL to retain in the agent handoff.
- Deprecated, non-Earth, missing, or equally ranked conflicting coordinates are rejected.
- An ambiguous name lookup fails with candidate QIDs. Review the candidates and rerun with
  the exact QID; never choose a place from name similarity alone.
- Add coordinates only after the row's named city/country or institution has been verified.

### `scripts/enrich.py`

Wikidata/Wikipedia identity and biography helper for the legacy 26-column CSV workflow. It
can resolve a laureate through Wikipedia page properties and Wikidata, verify the match
against birth year or award received, and retrieve blank type/birth/sex/death fields.

Safe preview:

`uv run scripts/enrich.py crafoord.csv --dry-run --limit 5`

- Always use `--dry-run` for verification/retrieval work under the current SQLite workflow.
- Stdout is one JSON document for the agent. Progress messages are written separately to
  stderr.
- Each confirmed result contains the exact `award_record_id`, match reason, Wikidata source
  URL, and an `updates` object ready for guarded blank-only SQLite updates.
- The `updates` object names the entity identifier `laureate_wikidata_qid` and never asks an
  agent to place it in `source_laureate_id`.
- Abstained results contain an empty `updates` object and the reason confirmation failed.
- The tool abstains when it cannot confirm identity and reports conflicts instead of
  guessing.
- Name-to-QID resolutions are cached in `<dataset>.enrich-cache.json`.
- Without `--dry-run`, it rewrites the CSV and cache. Data agents must not use write mode.
- The current tool writes a Wikidata QID into CSV `source_laureate_id`; the SQLite schema
  instead reserves `source_laureate_id` for the award source and stores the entity QID in
  `laureate_wikidata_qid`. Do not use write mode until the tool is adapted to SQLite.
- It intentionally does not retrieve affiliations, citizenship, coordinates, motivations,
  or field/language values.

The dataset-specific `scripts/enrich_breakthrough.py`, `scripts/enrich_crafoord.py`, and
`scripts/enrich_fields.py` also write CSVs and are legacy helpers. Do not run them during
SQLite enrichment.

### `scripts/import_sqlite.py`

Builds `awards.sqlite3` from all 13 canonical CSV snapshots:

`uv run scripts/import_sqlite.py`

- Validates the exact CSV header, field counts, required identity fields, ID prefixes, and
  global ID uniqueness before replacing the database.
- Preserves every CSV value as text.
- Adds the normalized prize family name and verified award QID.
- Copies QID-shaped legacy `source_laureate_id` values into `laureate_wikidata_qid` without
  deleting the original source value.
- Builds indexes for prize/category/year, name, and nonblank laureate QID.
- Writes a temporary database, runs `PRAGMA integrity_check`, and replaces the target only
  after a successful import.
- This is a rebuild tool, not an enrichment tool. Do not run it after agents begin writing
  verified data directly to SQLite.

### Other references

- `scripts/extract-wikipedia.md` documents the preferred Wikidata-first extraction method:
  structured Wikidata claims first, Wikipedia API text second, and model extraction only
  for facts still embedded in prose.
- `scripts/audit_deep.py` audits CSV snapshots only. It does not validate SQLite changes.
- Use `sqlite3 awards.sqlite3` for read-only inspection and exact row updates. Select rows by
  `award_record_id`, never by name alone.

main award files (sources under each — read these instead of searching):
- abel_prize.csv
  official:   https://abelprize.no
  wikipedia:  https://en.wikipedia.org/wiki/Abel_Prize
- breakthrough.csv
  official:   https://breakthroughprize.org
  wikipedia:  https://en.wikipedia.org/wiki/Breakthrough_Prize
- crafoord.csv
  official:   https://www.crafoordprize.se
  wikipedia:  https://en.wikipedia.org/wiki/Crafoord_Prize
- fields.csv
  official:   https://www.mathunion.org/imu-awards/fields-medal
  wikipedia:  https://en.wikipedia.org/wiki/Fields_Medal
- japan_prize.csv
  official:   https://www.japanprize.jp/en/
  wikipedia:  https://en.wikipedia.org/wiki/Japan_Prize
- kyoto_prize.csv
  official:   https://www.kyotoprize.org/en/
  wikipedia:  https://en.wikipedia.org/wiki/Kyoto_Prize
- lasker_awards.csv
  official:   https://laskerfoundation.org
  wikipedia:  https://en.wikipedia.org/wiki/Lasker_Award
- max_planck_medal.csv
  official:   https://www.dpg-physik.de/auszeichnungen/dpg-preise/max-planck-medaille
  wikipedia:  https://en.wikipedia.org/wiki/Max_Planck_Medal
- nobel.csv
  official:   https://www.nobelprize.org
  wikipedia:  https://en.wikipedia.org/wiki/List_of_Nobel_laureates
- shaw_prize.csv
  official:   https://www.shawprize.org
  wikipedia:  https://en.wikipedia.org/wiki/Shaw_Prize
- turing_award.csv
  official:   https://amturing.acm.org
  wikipedia:  https://en.wikipedia.org/wiki/Turing_Award
- wolf_prize.csv
  official:   https://wolffund.org.il
  wikipedia:  https://en.wikipedia.org/wiki/Wolf_Prize
