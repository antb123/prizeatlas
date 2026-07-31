# Universities with the most award-winning laureates — 20260729

A ranking page limited to universities and colleges, with an Overall view and a By country view.
The title is deliberate: the data measures **award-time affiliations**, not teaching quality or research output.

## 1. Does this need a new field? Yes — `affiliations.kind`

The database has no institution type. Classifying by name alone fails in both directions on the current data
(596 distinct affiliation QIDs currently referenced):

| Name rule says | Reality | Examples in the data |
|---|---|---|
| miss (no keyword) | university | ETH Zurich (18), Weizmann Institute of Science (13), Karolinska Institutet (8), LMU Munich (10), Collège de France (12) |
| hit (has "University") | hospital / centre | University of Chicago Medical Center, NYU Medical Center, UT Southwestern Medical Center, University of Virginia Medical Center, Douglas Mental Health University Institute |
| miss, correctly | not a university | Max Planck Society (49), Institute for Advanced Study (26), NIH (26), HHMI (21), CERN (19), Bell Labs (13) |

A keyword list plus per-name overrides inside `build.py` would encode ~20 editorial judgements as code and leave them
invisible to every other tool. One stored field states the judgement once, is greppable, and serves the later
"Top institutes" / "Top hospitals" cuts for free.

```
Wikidata P31  ──classify_affiliations.py──▶  affiliations.kind  ──build.py──▶  /universities/
                                                  ▲
                                    datasets/affiliation_kinds.tsv (manual overrides)
```

### Schema

```sql
ALTER TABLE affiliations ADD COLUMN kind TEXT NOT NULL DEFAULT '';
```

`kind` ∈ `university | institute | hospital | company | government | other | ''` (blank = unclassified, excluded from the page).
Only `university` is read by this feature.

### Files

- `datasets/scripts/classify_affiliations.py:37-137` — union the QIDs used by `awards` and
  `award_extra_affiliations`, fetch each item's **P31**, resolve its English label, map that label to one of
  the six nonblank kinds, and insert or update the QID's `affiliations` profile. The command is dry-run by default;
  `--apply` adds the column when needed and writes the classifications.
- `datasets/affiliation_kinds.tsv` (new) — `affiliation_wikidata_qid`, `affiliation_name`, `kind`. Loaded last, wins over
  P31. Holds only five reviewed disagreements: Weizmann Institute of Science, Baylor College of Medicine, New York
  Medical College, Medical College of Georgia, and Connaught Laboratories.
- `datasets/scripts/validate_awards.py` — assert every `kind` is one of the seven values.

## 2. Pages

Two routes. Country detail is not duplicated — `/countries/affiliations/{country}/` already exists for all institutions.

```
/universities/            Overall   top 40, tabs: Overall | By country
/universities/countries/  By country  each country, its universities, top 10 each
```

### `datasets/website/build.py`

| Line | Change |
|---|---|
| 42-70 `TEMPLATES` | add `"universities.html"`, `"university_countries.html"` |
| 82-91 constants | add `UNIVERSITIES_ROUTE = "/universities/"`, `UNIVERSITY_COUNTRIES_ROUTE = "/universities/countries/"`, `UNIVERSITY_ROWS = 40`, `COUNTRY_UNIVERSITY_ROWS = 10` |
| 227-237 `AffiliationProfile` | add `kind: str` |
| 786-789, 832-840 `read_database` | select and carry `kind` |
| 1983-2033 | `plan_university_pages(affiliations) -> list[PageJob]` — filter `affiliation.profile and affiliation.profile.kind == "university"`, reuse the existing `plan_affiliation_countries()` on the filtered list for the by-country view, emit the two jobs |
| 2263 `create_site_plan` | `jobs.extend(plan_university_pages(affiliations))` |
| 2492-2494 `_render_job` | pass `universities_route`, `university_countries_route` |
| 2412-2413 `write_llms_txt` "Where to start" | one bullet for `/universities/` |

No new counting logic: `plan_affiliations()` (1031) already produces laureate counts, units, subjects and routes;
this is a filter over its output. Rows link to the existing `/affiliations/{slug}/` pages.

### Templates — `datasets/website/templates/`

`universities.html`, `university_countries.html`, both modelled on `affiliations.html` and `affiliation_country.html`
(same `rank-list` / `rank-count` markup, same two-tab `view-tabs` nav as `affiliations.html:3-6`).

Header copy, both pages:

> **Universities with the most award-winning laureates**
> Universities and colleges only — institutes, laboratories, hospitals and companies are ranked separately under Institutions.
> *Caveat:* an affiliation is the one recorded at the time of the award, not a whole career, so this measures where
> recognized work was done rather than a university's teaching or research quality.

`base.html:29` — nav keeps one **Institutions** entry; the universities page is reached from its tab row, not a new
top-level link.

## 3. Verify

1. From `datasets/`, `uv run scripts/classify_affiliations.py` classifies every currently referenced QID and previews
   the totals plus a sample; after a database backup, `uv run scripts/classify_affiliations.py --apply` writes them.
   `select kind, count(*) from affiliations group by kind` shows no blank rows among the top 40 institutions.
2. Spot-check the ten names in the table above land in the right `kind`.
3. From `datasets/`, `uv run website/build.py --base-url https://prizeatlas.org` → `/universities/` and
   `/universities/countries/` exist in `website/dist/`, appear in
   `sitemap.xml`, and the overall list contains Harvard, MIT, ETH Zurich but not Max Planck Society, NIH, CERN, Bell Labs.
4. Every row's link resolves to an existing `/affiliations/{slug}/` page.
