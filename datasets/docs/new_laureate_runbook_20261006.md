# Adding new laureates — runbook (20261006)

Add a new year's laureates for any prize family to `awards.sqlite3`: search, validate, insert, enrich (identity, birth place, affiliation, coordinates), validate, rebuild the website.
The steps are the same for every family; the table below holds the only per-family facts. Rules live in `AGENTS.md` and `docs/datasets-affiliation-records-20260728.md`; this file only orders them.
Official source URLs per family: `AGENTS.md`, "award families". Worked example: `docs/nobel-medicine-20261006.md`. Run everything from `datasets/`. Keep previews and scratch files out of the repo.
Known tooling and data problems the steps work around are tracked in `docs/new_laureate_runbook_todo_20261006.md`.
A prize family not in the table is a different job: `docs/contributing-prizes.md` (it also needs an `award_ranking.toml` entry).

```
1 Search → 2 Backup → 3 Insert → 4 QID → 5 Person enrich → 6 Affiliation + coordinates → 7 Validate → 8 Website + commit
```

| prefix (`<p>`) | `prize_name` | `award_wikidata_qid` | formal categories | `source_laureate_id` |
|---|---|---|---|---|
| `nobel` | Nobel Prize (Economics: see AGENTS.md, `Q47170`) | `Q7191` | yes | official API id |
| `wolf_prize` | Wolf Prize | `Q739936` | yes | blank |
| `abel_prize` | Abel Prize | `Q188184` | none: blank `category`, blank `field_language` and `biographical_note` | blank |
| `breakthrough` | Breakthrough Prize | `Q17278140` | yes (a `year` may read `2026 (special)`; copy the family's form) | blank |
| `fields` / `turing_award` / `max_planck_medal` / `millennium_technology_prize` | Fields Medal / Turing Award / Max Planck Medal / Millennium Technology Prize | `Q28835` / `Q185667` / `Q317038` / `Q1853663` | none: blank `category` | blank |
| `crafoord` | Crafoord Prize | `Q583069` | yes | official id |
| `gairdner_international_award` | Canada Gairdner International Award | `Q1031994` | none: blank `category` | official id |
| `brain_prize` | The Brain Prize | `Q18357422` | none: blank `category` | blank |
| `japan_prize` / `kyoto_prize` / `kavli_prize` | Japan Prize / Kyoto Prize / Kavli Prize | `Q908745` / `Q658444` / `Q1094530` | yes (Japan's field names change yearly; copy the source's) | blank |
| `lasker_awards` | Lasker Award | `Q921415` | yes (the four award names) | blank |
| `shaw_prize` | Shaw Prize | `Q584250` | yes | official id on some rows, else blank |

Two conventions need no table: copy the new row's `prize`, `category`, `year` form, and `prize_share` style from the family's latest rows, and take the next id from `max`, never from `count` (ids are not contiguous):

```sql
SELECT award_record_id, year, category, prize, prize_name, award_wikidata_qid, prize_share, source_laureate_id FROM awards WHERE award_record_id LIKE '<p>-%' ORDER BY award_record_id DESC LIMIT 5;
```

`prize` varies by family (`The Nobel Prize in Physics 2026`, `Wolf Prize`, `Breakthrough Prize in Fundamental Physics`). `prize_share` comes from the source; leave it blank when the source does not state it
(Wolf's old rows use a whole-year denominator; do not copy that). Never write a placeholder into `category`.

## 1. Search

What is missing? `SELECT category, count(*) FROM awards WHERE award_record_id LIKE '<p>-%' AND year = '2026' GROUP BY 1;` Check the official site for the announcement date; Nobel runs a category a day in early October, most others once a year.

Only Nobel has an API. For every other family, read the year's roster on the official site in full (name, category, citation, institution as printed); not news articles or search snippets.
Nobel (category codes `phy che med lit pea eco`; use `curl -L`, the `/2/` URLs redirect to `/2.1/`):

```
curl -sL 'https://api.nobelprize.org/2.1/nobelPrizes?nobelPrizeYear=2026&nobelPrizeCategory=med' | jq -c '.nobelPrizes[].laureates[] | {id, name: (.knownName.en // .orgName.en), portion, motivation: .motivation.en}'
curl -sL 'https://api.nobelprize.org/2.1/laureate/<id>' | jq -c '.[0] | {wd: .wikidata.id, born: .birth.date, city: .birth.place.city.en, country: .birth.place.country.en, sex: .gender, aff: [.nobelPrizes[].affiliations[]?.name.en]}'
```

Result: one list of `year, category, name, motivation, share, source id, institution, URL`. Keep it in scratch until step 8.

## 2. Backup and baseline

```
cp awards.sqlite3 awards.sqlite3.$(date +%Y%m%d)-<what>.bak
uv run scripts/validate_awards.py --detail 200 > before.txt        # scratch; diffed in step 7
```

## 3. Insert

One person per row; a team or institution is one `Organization` row with no birth, sex or death data. New ids continue the prefix; never renumber. Normalise at insert: `Boston, MA / USA` → `Boston` / `United States`, `male` → `Male`, dates ISO.

```sql
BEGIN IMMEDIATE;
SELECT count(*) FROM awards WHERE award_record_id IN ('nobel-001030','nobel-001031');   -- must be 0, else ROLLBACK; and stop
INSERT INTO awards (award_record_id, year, category, prize, prize_name, award_wikidata_qid, motivation, prize_share, source_laureate_id, laureate_type, full_name)
VALUES ('nobel-001030', '2026', 'Physics', 'The Nobel Prize in Physics 2026', 'Nobel Prize', 'Q7191', 'for …', '1/2', '1064', 'Individual', '…');   -- Nobel example
COMMIT;
```

Other families: fill `prize`, `category`, `source_laureate_id`, `prize_share` as the table and the latest-rows query above say (blank, where the family has none). Then `PRAGMA integrity_check;` must print `ok`, and the row count must equal old + inserted
(`ATTACH '<backup>' AS old; SELECT count(*) FROM (SELECT * FROM old.awards EXCEPT SELECT * FROM main.awards);` must be 0).

## 4. Laureate QID

Nobel: the API's `wikidata.id`. Every other family: find it, confirm it, write it. Never match on name alone; blank beats wrong.
`enrich.py` can resolve a QID itself, but without a `birth_year` on the row it abstains (tested on Wolf rows): its award anchor is the family QID, and people carry the category item, e.g. `Wolf Prize in Physics`.
A roster rarely gives a birth year, so do it by hand:

```
W='https://www.wikidata.org/w/api.php'
curl -s "$W?action=wbsearchentities&search=<name>&language=en&limit=5&format=json" | jq -c '.search[] | {id,label,description}'      # candidates
ids=$(curl -s "$W?action=wbgetentities&ids=Q…&props=claims&format=json" | jq -r '.entities[].claims.P166[].mainsnak.datavalue.value.id' | paste -sd'|')
curl -s "$W?action=wbgetentities&ids=$ids&props=labels&languages=en&format=json" | jq -r '.entities[].labels.en.value'                 # awards held
```

Confirm: the awards held include this prize (or its category item) and the field and birth year fit the roster. The label may differ from the roster spelling. Then write it, guarded:

```sql
UPDATE awards SET laureate_wikidata_qid = 'Q…' WHERE award_record_id = '…' AND COALESCE(laureate_wikidata_qid,'') = '';
```

If the person already has another award in the DB, the QID must equal theirs. Not sure: leave blank and say so in the note.

## 5. Person enrichment

```
cp awards.sqlite3 awards.sqlite3.$(date +%Y%m%d-%H%M%S).enrich.bak
uv run scripts/enrich.py --db awards.sqlite3 --record-id nobel-001030 --record-id nobel-001031 > enrich-report.json      # every id explicit; never --all
```

With a known QID it fills only blank type, birth date/year, birth city/country, sex, death. Read the report. Check the places, because Wikidata's birth place is sometimes the country:

```sql
SELECT award_record_id, birth_city, birth_country FROM awards WHERE year = '2026' AND (birth_city = birth_country OR birth_city LIKE '%,%');   -- fix by hand or blank the city
```

`birth_city` is the city alone, today's name; `birth_country` today's country. Anyone who has died needs `death_date`. Then ORCID/OpenAlex author ids: `uv run scripts/lookup_authors.py --db awards.sqlite3 --record-id <id>` previews;
add `--apply` only after review (it repeats the live lookup, it does not replay the preview). `high_school_subject`: copy what existing rows of the same prize and category carry, by guarded `UPDATE`, or leave blank.
Do not run `scripts/set_award_subjects.py` without `--dry-run`: it rewrites existing rows.

## 6. Affiliation and coordinates

Nothing here is automated; each value is hand-written per `award_record_id` and blank-guarded. The institution is the one at the time of the award.

1. **Name:** from the award source (the Nobel API `aff`, the Wolf roster). `affiliation_name` is the English Wikipedia title of the parent institution, not the unit (unit → `affiliation_sub_name`).
2. **QID:** resolve to the parent institution and confirm it is the one on this row. If the name search fails, search Wikidata by label and rerun with the exact QID.
   `uv run scripts/lookup_coordinates.py "<institution>" --country "<country>"` (or `… Q… --country …`) prints `wikidata_id`, `description`, and `dataset_coordinates`.
   Reuse an existing spelling, QID, city, and coordinates when the DB already holds the institution: `SELECT affiliation_name, affiliation_wikidata_qid, affiliation_city, affiliation_coordinates, count(*) FROM awards WHERE affiliation_name LIKE '%<x>%' GROUP BY 1,2,3,4;`
3. **City and country:** today's names, city alone. From the award source, else the institution's Wikipedia article.
4. **Coordinates** (`longitude,latitude`, four decimals, institution's own point): take `dataset_coordinates` from step 2, then check it against a second source.
   ```
   uv run scripts/lookup_nominatim.py --city "<city>" --country "<country>"       # same place, within a km or so; digits will differ
   uv run scripts/reverse_nominatim.py --coordinates "<longitude>,<latitude>"     # country_code must match the row's country (the name comes back in the local language)
   ```
   Sources disagree: leave the cell blank. The same trio gives `birth_coordinates` from the verified birth city (optional; blank is acceptable).
5. **Write:**
   ```sql
   UPDATE awards SET affiliation_name = 'Stanford University', affiliation_city = 'Stanford', affiliation_country = 'United States',
          affiliation_coordinates = '-122.1700,37.4275', affiliation_wikidata_qid = 'Q41506'
    WHERE award_record_id = 'nobel-001027' AND affiliation_name = '' AND affiliation_city = '' AND affiliation_country = ''
      AND affiliation_coordinates = '' AND COALESCE(affiliation_wikidata_qid,'') = '';
   ```
6. **A second affiliation** (Deisseroth: HHMI and Stanford) is never a hand `INSERT`: add a reviewed row to `award_extra_affiliations.tsv`, then `load_extra_affiliations.py --dry-run`, then without the flag (backup first; the load replaces the whole table).
   A new spelling or unit goes into `AFFILIATIONS` in `scripts/normalize_affiliations.py`; run it dry first. Details: affiliation doc §4 to §6.
7. **ROR and OpenAlex** (position 1): `lookup_ror.py --db awards.sqlite3 --record-id <id> > ror.json`, review, back up, `--apply ror.json`; then the same with `lookup_openalex.py`. Affiliation doc §5.2 and §5.3.

A blank affiliation QID is unfinished work, not a settled value.

## 7. Validate

```
sqlite3 awards.sqlite3 "PRAGMA integrity_check;"                      # ok
uv run scripts/validate_awards.py --detail 200 > after.txt; diff before.txt after.txt     # only the baseline failures; it reads awards and award_extra_affiliations
uv run scripts/normalize_affiliations.py                              # dry run; no new merges
uv run pytest tests/ && uv run ruff check
```

Compare the diff by group, not by count. `scripts/check_coordinates.sql` is named in `AGENTS.md` but missing from the checkout; the two-source check in step 6 stands in for it.

## 8. Website and commit

```
uv run website/build.py --base-url https://example.org/awards/ --home-only      # fails first if a new country, category or prize name lacks catalogue entries
uv run website/build.py --base-url https://example.org/awards/
```

If the check fails, regenerate the catalogues named in `AGENTS.md` ("static awards website": `fetch_wikidata_labels.py`, `translate_catalogue.py es|fr|ja`), review them, and commit them with the data.
Look at `website/dist/<prize>/winners/`, one new person page, one new institution page, `/explorer/`.

Write the run note `docs/<prize>_<yyyymmdd>.md` like `docs/nobel-medicine-20261006.md`: records added with source ids and QIDs, URLs used, fields left blank and why, backups, validator diff, pre-existing defects noticed but not changed.
Commit by name, without `website/dist/`, `*.bak`, or `../awards.sqlite3`, and with no tool-attribution lines in the message:

```
git add awards.sqlite3 award_extra_affiliations.tsv docs/<note>.md [website/i18n/*.toml if changed]
git commit -m "Add 2026 <prize> laureates" && git push
git rev-parse HEAD origin/master                                      # the two hashes must match
```
