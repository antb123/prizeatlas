one row per laureate/recipient
places - use todays name, country, location

- git currently don't use branches!!

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
- every affiliation carries a Wikidata QID. an affiliation with no QID cannot be linked,
  logoed, mapped, or merged with the same institution under another spelling, so treat a
  blank QID as unfinished work rather than a settled value. the QID identifies the ranked
  parent in `affiliation_name`, never the unit in `affiliation_sub_name`. resolve it per row
  and confirm the item is the institution on that row; never copy a QID from a same-named row.
- `affiliation_name` is the institution's English Wikipedia article title. wikipedia is the
  naming authority: `Rockefeller University` not `The Rockefeller University`,
  `University of Colorado Boulder` not `University of Colorado, Boulder`,
  `Memorial Sloan Kettering Cancer Center` unhyphenated. take the title from the QID's
  `sitelinks.enwiki`, not from the wikidata label, which often differs. an institution with
  no english article keeps its official name, recorded once and spelled the same everywhere.
- if a person has died, `death_date` (and place, if known) must be filled; blank death for
  the living. cross-check the "(YYYY–YYYY)" hint in `biographical_note` when present.
- `birth_year` is optional when a complete `birth_date` already supplies it.
- add `birth_coordinates` / `affiliation_coordinates` only after the named place is verified.
- do not infer `prize_share` or death details for the living.
- Organizations carry no birth/sex/death data.
- `source_laureate_id` is only a stable identifier explicitly assigned by the official award
  source or its API. It is not a profile URL, URL slug, Wikipedia/Wikidata identifier, or an
  identifier invented from the name/year. Leave it blank when the source exposes no ID.
- When an award has no formal categories, leave `category` blank. Never write `N/A`,
  `Not applicable`, the prize name, or a derived subject area as a placeholder.
- `field_language` is source-specific: an explicitly supplied research/peace/economics field
  or a literature laureate's writing language. Do not derive it from a laureate's work,
  occupation, department, or motivation. Leave it blank for Abel Prize records.
- `biographical_note` preserves a concise note already supplied by a source dataset, such as
  a parenthesized lifespan or source birth text. Do not generate, summarize, or copy a prose
  biography into it. Leave it blank for Abel Prize records.

## identity, institution, and provenance policy

- Key each person to one `laureate_wikidata_qid` where the evidence supports a unique match.
  Never identify a researcher from name alone: a wrong match is worse than a missing one.
  Citation metrics appear only for records confidently linked to the correct researcher.
- Reconcile institutions to the Research Organization Registry (ROR) where possible, with
  explicit alias resolution such as `MIT` → `Massachusetts Institute of Technology`, so
  constituent units roll up to their ranked parent. ROR identity supplements the existing
  Wikidata-QID and English-Wikipedia-title rules; it does not replace them, and a ROR ID must
  never be written into `affiliation_wikidata_qid`.
- Assemble award records from the Nobel Prize API, Wikidata property P166, official rosters,
  and curated catalogues. Source citation metrics from OpenAlex and researcher identifiers
  from ORCID.
- Keep source and confidence at the individual award-record or claim level. Write them only
  to dedicated schema fields; while such fields do not exist, retain them in the research
  handoff and never overload `source_laureate_id`, `remarks`, or another unrelated column.

## current data target

- `awards.sqlite3` is the sole source of truth. The CSV snapshots are archived under `old/`
  and are no longer written to or read during enrichment.
- Data verification/retrieval agents write to `awards.sqlite3`, table `awards`, by exact
  `award_record_id`.
- The SQLite table preserves all 26 CSV columns and adds `prize_name`,
  `award_wikidata_qid`, and `laureate_wikidata_qid`.
- Affiliations are the exception to "one row holds everything": they span three tables and have their own entry,
  ownership, and validation rules. Read `docs/datasets-affiliation-records-20260728.md` before writing any
  `affiliation_*` value, adding a second affiliation, or running `scripts/normalize_affiliations.py`.
- `award_ranking` stores one curated website slug, official URL, prestige score, blurb, and reasoning entry per award
  family.
  `award_ranking.toml` is its complete source; load it with
  `uv run scripts/load_award_ranking.py` after backing up the database.
- Finish research before opening a write transaction. Keep transactions short and update
  blank cells only; guard each update against the cell's current blank value.
- Back up before any bulk run. There is no rebuild path — a lost database is lost work:

  `cp awards.sqlite3 awards.sqlite3.$(date +%Y%m%d).bak`

- Verify database health after writes:

  `sqlite3 awards.sqlite3 "PRAGMA integrity_check;"`

  The required result is exactly `ok`. This proves the file is not corrupt and says nothing
  about whether the data is right — for that see `scripts/check_coordinates.sql` and
  `docs/birth-coordinates-validation-20260725.md`.

## static awards website

Run the website build from this `datasets/` directory:

`uv run website/build.py --base-url https://example.org/awards/`

- One offline build publishes English at `/`, Spanish at `/es/`, and French at `/fr/`. Semantic route segments and
  category, country, and subject slugs are localized. Prize, person, institution, city, year, and award-recipient
  slug components stay canonical, and every page carries reciprocal `hreflang` links plus an equivalent-page
  language switcher.
- Committed catalogues live in `website/i18n/`: `en.toml` is the English source, `es.toml` and `fr.toml` are the
  translated catalogues with durable `reviewed` keys, and `labels.toml` holds optional exact-QID institution labels.
  Award motivations, biographical notes, institution descriptions, personal names, constituent-unit names, city
  names, dates, citations, and identifiers are never translated.
- Refresh institution labels explicitly with `uv run scripts/fetch_wikidata_labels.py`. Regenerate an unreviewed
  target catalogue explicitly with `uv run scripts/translate_catalogue.py es` or
  `uv run scripts/translate_catalogue.py fr`; see each command's `--help` for its authoring-time network and
  credential contract. The website builder itself never fetches labels or calls a translation provider.
- Catalogue coverage is closed for route segments, UI copy, ranking blurbs, prizes, categories, countries, subjects,
  and laureate types. Enrichment that introduces a new country, category, or prize name makes both the full build and
  `--home-only` fail until both target catalogues are regenerated, reviewed as needed, and committed.
- `awards.sqlite3` is read-only during website generation. Award records come from `awards`; stored prize routes and
  ranking copy come from `award_ranking`, whose complete seed is `award_ranking.toml`.
- `--base-url` is required and may include a deployment subpath. It supplies absolute canonical and sitemap URLs.
- Generated HTML, CSS, and sitemap output is written to `website/dist/`. Numbered sitemap files and a sitemap index
  are generated only when the single-sitemap limits are exceeded.
- `/{prize}/winners/` lists every recipient of one prize, oldest first, from `winners.html`. The prize page itself
  stops at `PRIZE_PAGE_YEARS`, and only prizes with standing categories have complete lists beneath them, so this is
  the one page that holds the whole roll of an uncategorized prize. It exists for crawlers and AI readers.
- Root `llms.txt`, `/es/llms.txt`, and `/fr/llms.txt` are the machine readers' localized guides: counts, URL patterns,
  every winner list named explicitly (per prize, per category, per subject), and the pages that carry embedded JSON.
  They are generated from the same locale plans as the pages, stay out of the sitemap, and are never hand-edited.
- The sitemap covers all three page plans while `awards.csv` and `robots.txt` remain shared at the root. Existing
  English share-image paths remain stable; Spanish and French share images live under `static/share/es/` and
  `static/share/fr/`.
- `--home-only` validates all catalogues but rewrites only the English root `dist/index.html`; it leaves localized
  pages and shared artifacts untouched. The single generated root `404.html` remains English because no locale-aware
  server error routing is part of the static build.
- `website/dist/`, `.dist-staging-*`, and `.dist-backup-*` are generated local state and MUST NOT be versioned.
- The builder uses only static files; it does not run an application server or modify the database.

## data explorer

- The explorer is part of the static awards website at `/explorer/` and is built by `website/build.py` with every
  other page. Its template is `website/templates/explorer.html`, and its population snapshot is
  `website/population.json`.
- Scoring: a laureate's points = sum of `award_ranking.score` / 100 over their award rows (a Nobel = 1.00, so two
  Nobels = 2.00). Prize shares are not discounted. Organizations are ranked alongside people with a badge.
- Identity follows `laureate_wikidata_qid`; any row without a QID stays unmerged as a single-award entry.
- The country chart counts distinct merged laureates per modern country, switchable between
  birth/death/affiliation/citizenship; affiliation and citizenship count a laureate under each listed country.
  A "Laureates per million" view divides birth-country laureates by the World Bank SP.POP.TOTL snapshot, counting
  each person once regardless of award count; Taiwan, Tibet, and Northern Cyprus have no figure and are skipped.
- The under-40 chart ranks laureates who won at least one award before 40 (age = award year − birth year) by
  total points.
- The leaderboard shows the top 7 (`TOP_N` in `website/templates/explorer.html`); search reveals all rows with true
  ranks.
- The explorer makes one optional browser request to `https://api.country.is/` to show the top laureates born in the
  visitor's detected country. Failure leaves an unavailable note and does not affect the rest of the page; a
  `?country=BE` query parameter overrides detection for testing.

## local lookup and enrichment tools

Run these commands from this `datasets/` directory.

### location lookup and validation

Use both Wikidata and Nominatim; never trust either alone:

1. Wikidata: `uv run scripts/lookup_coordinates.py "<place>" --country "<country>"`
2. Nominatim: `uv run scripts/lookup_nominatim.py --city "<city>" --country "<country>" [--state "<state>"]`
3. Validate: `uv run scripts/reverse_nominatim.py --coordinates "<longitude>,<latitude>"`

The reverse country must match the record. If the sources disagree, leave the coordinate unchanged.
Coordinates use `longitude,latitude` at four decimal places. Lookup tools print JSON and never update the database.

### `scripts/lookup_coordinates.py`

Read-only lookup for one city or institution. It resolves an exact English Wikipedia title
to its Wikidata item, or accepts a verified Wikidata QID directly. `--country` is required:

`uv run scripts/lookup_coordinates.py "University of Cambridge" --country "United Kingdom"`

`uv run scripts/lookup_coordinates.py Q35794 --country "United Kingdom"`

- `--country` is appended to the query, so `Ottawa --country "United States"` fails rather
  than silently returning Ontario. Expect roughly three quarters of bare city names to fail;
  read the error, find the QID, and rerun with it. Failing is the tool working.
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

Read from and apply updates to the migrated database:

`uv run scripts/enrich.py --db awards.sqlite3`

- Use `--db awards.sqlite3` with a required selector for enrichment under the current SQLite workflow. CSV input is a legacy dry-run interface only.
- Select exact rows with repeatable `--record-id <award_record_id>`, or select a target range with `--offset N --limit N`.
- Dataset tasks MUST pass every assigned `award_record_id` with repeatable `--record-id`; do not derive task ranges with `--limit` or `--offset` because living-person rechecks change target positions.
- A database run without a selector is rejected. `--all` is the explicit whole-database mode and MUST NOT be used for a bounded dataset task.
- Repeat `--record-id` once per assigned row:

  `uv run scripts/enrich.py --db awards.sqlite3 --record-id abel_prize-000006 --record-id abel_prize-000007`

- Stdout is one JSON document for the agent. Progress messages are written separately to
  stderr.
- Each confirmed result contains the exact `award_record_id`, match reason, Wikidata source
  URL, and an `updates` object ready for guarded blank-only SQLite updates.
- It returns the verified person or organization QID at
  `results[].updates.laureate_wikidata_qid` and the corresponding source URL at
  `results[].wikidata_url`.
- It does not return the award-family QID in each result because that value is already
  populated in SQLite `award_wikidata_qid`.
- It never asks an agent to place a Wikidata QID in `source_laureate_id`.
- Abstained results contain an empty `updates` object and the reason confirmation failed.
- The tool abstains when it cannot confirm identity and reports conflicts instead of
  guessing.
- Name-to-QID resolutions are cached in `<dataset>.enrich-cache.json`.
- `--db` reads the enrichment rows from SQLite, validates every report record ID, and applies all allowed nonblank updates in one transaction.
- Without `--dry-run` or `--db`, the legacy mode rewrites the CSV and cache and writes a Wikidata QID into CSV `source_laureate_id`. Data agents must not use that mode.
- It intentionally does not retrieve affiliations, citizenship, coordinates, motivations,
  or field/language values.

The dataset-specific `scripts/enrich_breakthrough.py`, `scripts/enrich_crafoord.py`, and
`scripts/enrich_fields.py` also write CSVs and are legacy helpers. Do not run them during
SQLite enrichment.

### `scripts/import_sqlite.py` — DELETED

Removed. It rebuilt `awards.sqlite3` from the CSV snapshots and would have destroyed every
coordinate and correction made since enrichment moved to SQLite. `awards.sqlite3` is the source
of truth and there is no import path back from CSV. The original build is recorded in git
history at `95e431d`; the CSV snapshots are archived under `old/`.

The schema therefore lives only in the database. Read it with
`sqlite3 awards.sqlite3 ".schema awards"`. `tests/test_enrich_json.py` keeps a local fixture
copy for its temporary databases.

### Other references

- `scripts/extract-wikipedia.md` documents the preferred Wikidata-first extraction method:
  structured Wikidata claims first, Wikipedia API text second, and model extraction only
  for facts still embedded in prose.
- `scripts/audit_deep.py` audits CSV snapshots only. It does not validate SQLite changes.
- `scripts/check_coordinates.sql` reports birth coordinates that point at the wrong place.
  Run it after every enrichment batch: `sqlite3 awards.sqlite3 < scripts/check_coordinates.sql`
- Use `sqlite3 awards.sqlite3` for read-only inspection and exact row updates. Select rows by
  `award_record_id`, never by name alone.

award families (sources under each — read these instead of searching). The CSVs are archived
under `old/`; the live data for each is the matching `award_record_id` prefix in SQLite:
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
- kavli_prize (SQLite prefix only; no legacy CSV)
  official:   https://www.kavliprize.org/
  wikipedia:  https://en.wikipedia.org/wiki/Kavli_Prize
- kyoto_prize.csv
  official:   https://www.kyotoprize.org/en/
  wikipedia:  https://en.wikipedia.org/wiki/Kyoto_Prize
- lasker_awards.csv
  official:   https://laskerfoundation.org
  wikipedia:  https://en.wikipedia.org/wiki/Lasker_Award
- max_planck_medal.csv
  official:   https://www.dpg-physik.de/auszeichnungen/dpg-preise/max-planck-medaille
  wikipedia:  https://en.wikipedia.org/wiki/Max_Planck_Medal
- millennium_technology_prize (SQLite prefix only; no legacy CSV)
  official:   https://millenniumprize.org/
  wikipedia:  https://en.wikipedia.org/wiki/Millennium_Technology_Prize
- nobel.csv
  official:   https://www.nobelprize.org
  wikipedia:  https://en.wikipedia.org/wiki/List_of_Nobel_laureates
  Economics rows use prize family `Sveriges Riksbank Prize in Economic Sciences`
  and award QID `Q47170`, not `Nobel Prize` / `Q7191`.
- shaw_prize.csv
  official:   https://www.shawprize.org
  wikipedia:  https://en.wikipedia.org/wiki/Shaw_Prize
- turing_award.csv
  official:   https://amturing.acm.org
  wikipedia:  https://en.wikipedia.org/wiki/Turing_Award
- wolf_prize.csv
  official:   https://wolffund.org.il
  wikipedia:  https://en.wikipedia.org/wiki/Wolf_Prize
