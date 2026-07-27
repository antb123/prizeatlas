# Affiliation data — TODO (20260727)

Branch `feat/map-mvp`. Database changes are applied and backed up but **not committed**.

## Done today

| Change | Rows | Backup |
|---|---|---|
| Filled blank `affiliation_city` from rows sharing identical coordinates | 101 | `awards.sqlite3.20260727-092629.city.bak` |
| Split Institut Pasteur de Tunis from Paris (`Q391083` → `Q3151790`, coords → Tunis) | 1 | `awards.sqlite3.20260727-093705.pasteur.bak` |
| Muon g−2: gave each site team its own laureate QID (CERN `Q42944`, Brookhaven `Q585777`, Fermilab `Q337641`) | 3 | `awards.sqlite3.*.muon.bak` |

Added `scripts/validate_awards.py` — 9 checks, read-only, exits 1 on the fatal ones. Nothing else in the repo was touched.

Site builds green: 8143 pages, 2374 people.

## Decisions made

1. **Organization laureates take their own institution's QID**, matching the four rows that already did this (WHO, Gavi, Sudbury Neutrino Observatory, Menninger). Three winners at three locations = three records, three QIDs, `1/9` each — the same shape as two humans splitting a prize.
2. **`awards` keeps its flat `affiliation_*` columns** in phase 1 of any normalization. New tables land additively; `build.py` gets rewritten later, not at the same time.
3. **No parser splits affiliation prose on commas.** `"University of California, Berkeley, Howard Hughes Medical Institute"` splits into a phantom "Berkeley". Match against known institution names longest-first instead; flag the remainder.

## Next — in order

1. **Audit the 101-row city fill.** It assumed identical coordinates = same place, which was later contradicted ("the coordinates are often wrong"). `validate_awards.py --check coords-shared-across-cities --detail 80` lists the 65 suspects; most are `Boston` / `Boston, MA` noise, the real errors are the ones where the *city names genuinely differ*. Two already found and fixed by hand: Institut Pasteur (Tunis on Paris coords), Rockefeller (a `Princeton, NJ` row on Manhattan coords).

2. **Add an extras table — do this before the full normalization.** Purely additive, reversible, breaks nothing on day one, and folds into `award_affiliations` later (extras become join rows, primary becomes rank 1). Preferred over migrating everything at once.

   ```sql
   CREATE TABLE award_extra_affiliations (
       award_record_id  TEXT NOT NULL REFERENCES awards(award_record_id),
       rank             INTEGER NOT NULL CHECK (rank >= 2),   -- 2nd, 3rd, 4th...
       affiliation_name TEXT NOT NULL,
       affiliation_wikidata_qid TEXT NOT NULL DEFAULT '',
       source           TEXT NOT NULL DEFAULT '',             -- 'remarks' | 'sub_name' | 'manual'
       PRIMARY KEY (award_record_id, rank)
   ) STRICT;
   ```

   No city/country/coordinates columns on purpose — those belong to the institution, not the award, and duplicating them recreates the drift that split Berkeley 34/28. Join by name to the primary rows for coordinates.

   Two things that must follow, or the table achieves nothing:
   - `website/build.py:871` (laureate count per affiliation) and `:906` (per subject) MUST read both sources. Miss them and HHMI still ranks 4.
   - `validate_awards.py`'s `institution-facts-disagree` check MUST cover the new table, or a name typed differently there reintroduces the split silently.

3. **Full normalization — later, once the extras table is populated and stable.** Stopped at Stage 0 when the muon fix took priority. Forks 1 and 2 are answered above; fork 3 dissolved — giving the muon rows their own QIDs made the `build.py` identity change unnecessary. Target schema:

   ```sql
   CREATE TABLE institutions (
       institution_id INTEGER PRIMARY KEY,
       name TEXT NOT NULL, sub_name TEXT NOT NULL DEFAULT '',
       city TEXT NOT NULL DEFAULT '', country TEXT NOT NULL DEFAULT '',
       coordinates TEXT NOT NULL DEFAULT '', wikidata_qid TEXT NOT NULL DEFAULT '',
       UNIQUE (name, sub_name),
       CHECK (coordinates = '' OR wikidata_qid <> '')     -- no QID, no lat/long
   ) STRICT;

   CREATE TABLE award_affiliations (
       award_record_id TEXT NOT NULL REFERENCES awards(award_record_id),
       institution_id  INTEGER NOT NULL REFERENCES institutions(institution_id),
       role TEXT NOT NULL DEFAULT '',
       PRIMARY KEY (award_record_id, institution_id)
   ) STRICT;
   ```

4. **Recover the second affiliations.** They exist already, in three hiding places, because the flat table has one affiliation slot:

   | Where | Count |
   |---|---|
   | `remarks` prose — "held roles at X **and Howard Hughes Medical Institute**" | 62 extracted |
   | `affiliation_sub_name` holding the real institution (UC campuses, MPI institutes) | 143 rows |
   | Jammed into `affiliation_name` (`Boston Children's Hospital/Harvard Medical School`) | ~15 rows |

   Extractor written and run: `<scratchpad>/extract_second_affiliations.py` → `second_affiliations.tsv`. **Not committed** — copy it into `scripts/` if it's worth keeping. 62 matched cleanly, 10 matched nothing, 35 left prose behind.

   Cost of leaving this: **Howard Hughes Medical Institute ranks 4 when it should rank 23.** Berkeley ranks 34 when it should rank 62 (28 rows are filed under `sub_name` with the UC *system* QID `Q184478`). Only one remark in the whole table is a genuine remark — Perelman declining the prize.

5. **~20 institutions in the remarks are not in the database at all** and need creating plus QID resolution by hand — Royal Society, Marine Biological Laboratory, Gladstone Institutes, Kavli Institute for Theoretical Physics, NewYork-Presbyterian, Brigham and Women's, Sinai Health, plus the Event Horizon Telescope's 13 member institutes. No parser invents these safely.

## Open risks

- **`validate_awards.py`'s fatal/backlog split is my judgement, not reviewed.** `affiliation-without-qid` (341) is marked backlog because it can't be a build gate today, but it's the question this whole session started from.
- **The QID audit's 443 "ok" is an upper bound.** It compares stored coordinates against Wikidata's for the same QID, so it cannot see a row that is confidently wrong in both — which is exactly what Institut Pasteur/Tunis was. The 27 mismatches it *did* find are all umbrella-QID artifacts (Max Planck Society across 18 cities, UC system across 6 campuses), where the coordinate is right and the QID is too coarse.
- **Pre-existing and untouched:** `The Ohio State University` carries both `Columbus` and `Columbus, OH`; 347 rows use the `City, ST` form against a 2236-row bare-city house style.
- `Q3151790` (Institut Pasteur de Tunis) has **no row in the `affiliations` table**, so it renders without logo or description until enriched.
