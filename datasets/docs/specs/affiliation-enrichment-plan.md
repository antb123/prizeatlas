# Task: Affiliation enrichment for `awards.sqlite3`

## Context

- Database: `awards.sqlite3`, table `awards` — sole source of truth. Run everything from the `datasets/` directory.
- Target columns: `affiliation_name`, `affiliation_city`, `affiliation_country` (not coordinates — separate later phase).
- Select rows by exact `award_record_id`. Never by name.

## Hard rules (from AGENTS.md)

- Fill blank cells only — never overwrite a curated value. Guard every UPDATE with `AND affiliation_name = ''`.
- Affiliation = institution **at time of award**. Individuals only: skip all `laureate_type = 'Organization'` rows (existing org affiliations are grandfathered — do not touch).
- Leave blank when unsure. Do not guess or infer. "No affiliation at award" is an explicit research finding, not a reason to fill from a later-career employer.
- Modern country names only (e.g. `United States`, not `USA`; `Russia`, not `USSR`).
- Multiple simultaneous affiliations use the existing parallel-list convention: `affiliation_name = 'A; B'`, `affiliation_city = 'X; Y'`, `affiliation_country = 'P; Q'`.
- Back up before every batch: `cp awards.sqlite3 awards.sqlite3.$(date +%Y%m%d-%H%M%S).affiliations-<batch>.bak`
- After every batch: `sqlite3 awards.sqlite3 "PRAGMA integrity_check;"` must return exactly `ok`.

## Scope (current blanks, individuals)

| Phase | Family | Rows | Expectation |
|---|---|---|---|
| 1 | Canada Gairdner International Award | 237 | high fill rate — researchers |
| 2 | Shaw Prize | 75 | high fill rate — scientists |
| 3 | Nobel Prize | 234 | verify-only: official source has no affiliation for these rows (Literature/Peace/retirees); most stay blank after verification |
| 4 | Wolf Prize (all Arts) | 58 | mostly "confirmed none" — artists |

Follow-up phases after these: 241 rows with city+country but no name; 28 rows with name only; 636 rows with name+city but no country (Gairdner winner pages can backfill city/country via their `position` line); then coordinates via `uv run scripts/lookup_coordinates.py "Name" --country "C"` (note: `scripts/check_coordinates.sql` referenced in AGENTS.md does not exist — recreate it).

## Validated source map (tested 2026-07-25)

- **Wikidata `employer` (P108)** — primary. Accept when a statement's period covers the award year, or it's the sole employer and biography confirms the period. Get labels via `wbgetentities`.
- **Wikipedia prose** — required to date-anchor undated Wikidata employers (e.g. "at UC Berkeley 1987–2001").
- **Nobel API v2.1** (`api.nobelprize.org/2.1/laureate/<source_laureate_id>`) — returns no `affiliations` for the blank rows; use only to *confirm* "none".
- **Wolf Foundation laureate pages** — no affiliation field for arts laureates; confirmation of "none" only.
- **Gairdner winner pages** (`gairdner.org/winner/<name-slug>`) — contain only `<span class='position'>City, State, Country</span>`; no institution name. Use for city/country confirmation, never for names.

## Worked pilot (approved values — execute first, 3 rows)

| award_record_id | affiliation_name | affiliation_city | affiliation_country | anchor |
|---|---|---|---|---|
| gairdner_international_award-000236 | Fox Chase Cancer Center | Philadelphia | United States | Wikidata sole employer, 1976–2011 covers 1997 |
| gairdner_international_award-000237 | University of California, Berkeley | Berkeley | United States | Wikipedia prose: Berkeley 1987–2001 covers 1997 |
| gairdner_international_award-000238 | Sanford Burnham Prebys Medical Discovery Institute | La Jolla | United States | Wikidata dated 1979–2020 covers 1997 |

## Per-batch protocol

1. Backup (see above).
2. Research sub-batch (~25 rows) fully **before** writing. Produce a research file, one line per row: `award_record_id | name | city | country | source URL | fill | confirmed-none | abstain:<reason>`.
3. One short transaction per sub-batch:

```sql
BEGIN;
UPDATE awards SET affiliation_name='…', affiliation_city='…', affiliation_country='…'
  WHERE award_record_id='…' AND affiliation_name='';
-- …
COMMIT;
```

4. `PRAGMA integrity_check` = `ok`; recount blanks per family; report fills / confirmed-none / abstained with reasons. Another process edits this database concurrently — the `WHERE affiliation_name = ''` guard keeps every statement idempotent; never remove the guard.
