# Runbook TODOs — issues found while writing `new_laureate_runbook_20261006.md`

Each item was found while writing or testing the runbook. None is fixed; the runbook works around it, and each is handled separately.
Evidence is what was observed on 20261006 (tests ran on a scratch copy of the database).

## Scripts

- [ ] **`enrich.py` abstains for non-Nobel prizes when `birth_year` is blank.** In `--db` mode its award anchor is `awards.award_wikidata_qid` (the family, e.g. `Q739936`), but people carry the category item
  (`Wolf Prize in Physics`), so `classify()` returns "human but no anchor". Tested on `wolf_prize-000391` and `-000388` with identity blanked: both abstained. Rosters rarely give a birth year, so this hits every family except Nobel.
  `scripts/enrich.py:279-293`, `:582`. Runbook step 4 does the QID by hand.
- [ ] **`enrich.py` writes a country into `birth_city`.** When Wikidata's birth place (P19) is a country item, `place_city_country()` returns the country as the city. Tested: `Mordehai Heiblum` → `birth_city = Israel`.
  11 rows already hold `birth_city = birth_country`, 5 of them Wolf (`wolf_prize-000391` among them). `scripts/enrich.py:251-258`. Runbook step 5 has a query to catch it; the 11 existing rows need review.
- [ ] **`enrich.py --db` overwrites `laureate_wikidata_qid` unconditionally.** The apply `UPDATE` uses `"laureate_wikidata_qid" = ?` with no blank guard, unlike every other field. Conflicts with the blank-only rule in `AGENTS.md`.
  `scripts/enrich.py:469-472`. Harmless today only because a known QID is reused as-is.
- [ ] **`set_award_subjects.py` is not blank-only.** It updates every row whose stored `high_school_subject` differs from the computed one, across the whole table, and the Kyoto map is hard-coded by record id. `scripts/set_award_subjects.py:176-179`.
  Needs a blank-only mode or a per-record selector. Runbook step 5 says dry-run only.
- [ ] **`enrich_affiliations.py` and `classify_affiliations.py` ignore `--help`.** They have no argparse, so `--help` starts a real network run (dry run by default, so no writes). Add argparse with `--help`.
- [ ] **`reverse_nominatim.py` returns the country name in the local language** (`ישראל` for Israel), so the `AGENTS.md` rule "the reverse country must match the record" cannot be checked by name. `country_code` is usable. Return an English name or document the code comparison in `AGENTS.md`.

## Missing or stale documentation

- [ ] **`scripts/check_coordinates.sql` does not exist** but `AGENTS.md` (lines 91 and 258-259) tells agents to run it after every enrichment batch. Restore it or change `AGENTS.md`. The runbook uses the two-source check and `validate_awards.py` instead.
- [ ] **`docs/nobel-medicine-20261006.md` is stale.** It says affiliations and coordinates were left blank, but all three rows (`nobel-001027` to `-001029`) now carry affiliation names, QIDs, and coordinates. Update it or add a dated follow-up.
- [ ] **Nobel API URLs in that doc and elsewhere use `/2/`,** which redirects (302) to `/2.1/`. `curl` without `-L` returns an empty body. Use `/2.1/`.
- [ ] **`validate_awards.py` baseline numbers differ between docs:** 76 and 18 failing groups at 20260728 (`docs/datasets-affiliation-records-20260728.md`) against 57 and 2 on 20261006 (`docs/nobel-medicine-20261006.md`). Refresh the live counts.

## Data

- [ ] **Wolf `prize_share` uses a whole-year denominator** (`1/9` on three 2025 Physics rows for a three-person category), across 330 rows. `AGENTS.md` says not to infer `prize_share`. Decide whether to blank, recompute from the roster, or document the convention.
- [ ] **`brain_prize` rows hold SQL `NULL`** in `category` and `source_laureate_id` (51 rows) where other families use `''`. Normalise, or confirm the build treats both as blank.
- [ ] **Lasker birth data conflicts with Nobel:** `lasker_awards-000396` has Karl Deisseroth's birth year as 1975 (Nobel API: 1971-11-18); `lasker_awards-000397` has Peter Hegemann's birthplace as Ludwigshafen. Noted in `docs/nobel-medicine-20261006.md`, still unchanged.
- [ ] **Existing birth places that are countries** (see the `enrich.py` item above): 11 rows, review each by hand.

## Workspace

- [ ] **Stray untracked `awards.sqlite3` at the repository root** (`../awards.sqlite3`), separate from `datasets/awards.sqlite3`. Delete it or ignore it, and decide on the other untracked files (`cities.csv`, `cities_with_population.csv`, `mobile1.png`).

## Runbook follow-up

- [ ] **The runbook has not been run end to end.** Pieces were tested on a scratch copy (enrich, Wikidata QID search, coordinate lookups, Nobel API fields); the insert template, guarded `UPDATE`s, extras load, ROR/OpenAlex, build, and commit steps were checked by reading only. Do a full dry run on a scratch database with one real new row.
- [ ] **The external review's findings** (extras coverage, partial blank guard, handoff location, `lookup_authors.py --apply` wording, commit staging, push check) were folded into the rewrite; re-run the review on the shortened text.

## Noted, no action

- Record ids are not contiguous (`kyoto_prize` last id is `000128` with 87 rows), so the next id comes from `max(award_record_id)`, never `count(*)`. The runbook says so.
