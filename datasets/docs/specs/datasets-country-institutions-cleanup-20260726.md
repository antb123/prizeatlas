# People / institutions split — cleanup plan (20260726)

Covers the three commits that added the country split, the redesign of `/countries/affiliations/<slug>/`, and the
same split applied to subjects. One question runs through all of it: *where could I study this?*

| Commit | Title | Scope |
| --- | --- | --- |
| `2e7bf7a` | Split country pages by people and institutions | `InstitutionCountry`, two new templates, tab CSS, route rename |
| `72b1991` | Restore countries landing page | `country_views.html` at `/countries/` |
| `3a3889b` | Separate country view tabs | `\|` separator between tabs |

Route map as it stands:

```
/countries/                        country_views.html      (orphan — nothing links here)
/countries/born/                   countries.html          ← base.html nav "Countries"
/countries/born/<slug>/            country.html
/countries/affiliations/           affiliation_countries.html
/countries/affiliations/<slug>/    affiliation_country.html
```

---

## Terminology — frozen

`affiliation` stays exactly as it is: routes (`/affiliations/`, `/countries/affiliations/`), template filenames,
Python identifiers, SQL columns. No renames, and the existing visible labels stay as they are. New routes and
templates added by this plan follow the `affiliations` vocabulary already on disk, so nothing new diverges.

---

## Findings

**F1 — `/countries/` is unreachable.** `COUNTRY_ROOT_ROUTE` (`website/build.py:66`) is used only to emit the page
(`build.py:1318-1326`). It is never passed into the render context (`build.py:1639-1640`, `1669-1670`), and
`base.html:28` still points the nav at `countries_route` = `/countries/born/`. The page exists only in the sitemap.
Its breadcrumb `("Home", "Countries")` is also byte-identical to the one on `/countries/born/` (`build.py:1324` vs
`build.py:1336`), so two different pages claim the same crumb, and `/countries/born/<slug>/` (`build.py:1351`) skips
the root entirely.

**F2 — the tab nav is copy-pasted five times.** Identical five-line block in `countries.html:3-7`, `country.html:3-7`,
`affiliation_countries.html:3-7`, `affiliation_country.html:3-7`, `country_views.html:3-7`. Only `aria-current`
differs. The repo already uses a Jinja macro (`prize.html:2`), so there is a precedent to follow.

**F3 — counts on a country page are worldwide, not in-country.** `affiliation_country.html:18` renders
`affiliation.count`, which `plan_places` computes as the institution's global laureate union (`build.py:823`). An
institution recorded in two countries shows the same number on both pages. The header line
(`affiliation_country.html:11`) counts institutions, and the country's laureate total is never shown — it cannot be
summed from the rows anyway, because one laureate can appear at several institutions.

**F4 — the grouping re-derives what the record loop already knew.** `build.py:832-859` walks every award of every
affiliation a second time to recover `affiliation_country`, after `build.py:782-786` has already bucketed the same
records. `plan_places` now returns a three-tuple and does three unrelated jobs (`build.py:744-860`).

**F5 — two columns on a ranking page.** `affiliation_country.html:14` uses `.people-index`, which is
`columns: 2` (`style.css:583-589`). The other four index pages — `countries.html:15`, `affiliation_countries.html:16`,
`affiliations.html:11`, `subjects.html:9` — use the single-column `.rank-list` (`style.css:310`). This page is a
ranking, so it belongs in `.rank-list`.

**F6 — no shared country vocabulary between the two tabs.** Birth countries key on `record.birth_country`
(`build.py:764`); institution countries key on `record.affiliation_country` split on `;` (`build.py:835-840`). Nothing
checks that the same place is spelled the same way in both, so the tabs can disagree silently.

**F7 — published `/countries/<slug>/` URLs now 404.** The rename at `build.py:67` moved every country page under
`/countries/born/`. Static hosting, no redirect layer. Decision needed, not necessarily a fix.

**F8 — unrelated change rode along.** `2e7bf7a` also relaxed `normalize_base_url` to accept `http://localhost`
(`build.py:275`) and taught the link-check test to skip `#` anchors. Both are defensible; neither belongs in a commit
about country pages. Noted for the record only.

---

## Plan

Each step is independently committable and verified by the existing suite plus one added assertion.

**1. The base route is the default view (fixes F1 and F7 together).** Delete `country_views.html`, restore
`COUNTRIES_ROUTE = "/countries/"`, keep the other tab at `/countries/affiliations/`. Published `/countries/<slug>/`
URLs come back, the orphan interstitial disappears, and the shape extends to subjects unchanged:

```
/countries/                        people, the default view + tabs
/countries/<slug>/                 one country's laureates
/countries/affiliations/           institutions tab
/countries/affiliations/<slug>/    one country's institutions
```

One guard needed: no country may slugify to `affiliations`, else `/countries/affiliations/` is ambiguous. Add it
beside the existing slug guard at `build.py:777`.
→ *verify:* every page under `/countries/` is reachable from the nav in ≤2 clicks; `/countries/<slug>/` resolves again.

**2. Extract the tab bar.** One `_view_tabs.html` include taking `(people_route, institutions_route, current)`,
replacing all five copies — and reused verbatim by the subject pages in step 5. Register it in `TEMPLATES`
(`build.py:44-59`).
→ *verify:* existing `test_country_tabs_split_people_and_recorded_institutions` assertions on `aria-current` still pass.

**3. Split the grouping out of `plan_places`.** New `plan_affiliation_countries(affiliations)` keyed
`country → affiliation slug → set[laureate qid]`, so each row carries its **in-country** laureate count and the city
recorded for it in that country. `plan_places` returns to a two-tuple.
→ *verify:* new test — an institution recorded in two countries shows a per-country count, not its global one.

**4. Rank list, single column.** `affiliation_country.html` moves from `.people-index` to `.rank-list`, matching the
other four index pages. Fixes F5 and gives the rows a share bar for free.
→ *verify:* rendered page contains `class="rank-list"`; no `.people-index` outside `people.html` and `country.html`.

**5. Split subjects the same way** — detailed below.

**Not doing — F6 needs no guard.** Checked against the data: of every distinct `affiliation_country` value, only
*Hong Kong* and *Saudi Arabia* are absent from the birth-country vocabulary, and both are legitimate — no laureate on
record was born there. A membership assertion would fail the build on good data. The existing slug guards
(`build.py:777`, `843-846`) already catch the case that matters.

**Not doing — F8.** The `normalize_base_url` localhost relaxation stays; it is useful and already tested.

---

## Redesign: `/countries/affiliations/<slug>/`

The United States page is the stress case: **268 institutions, 1,142 awards**. Today each row is a name and a
worldwide laureate count, in two columns. For a student it answers nothing — not where the place is, not what it is
strong at, not how to apply.

Data on hand (from `awards.sqlite3`):

| Field | US coverage | Source |
| --- | --- | --- |
| `affiliation_city` | 228 / 268 institutions | `awards` table |
| Subjects | all | already on `Affiliation.subjects` (`build.py:810-813`) |
| Sub-units | where recorded | already on `Affiliation.units` |
| `application_url` | 98 / 268 institutions | `affiliations` table — 303 of 304 profiled rows have one |

Proposed row, reusing `.rank-list` exactly as `affiliations.html:11-27` does:

```
 1  Harvard University                                    28 laureates ▓▓▓▓▓▓▓▓
    Cambridge, MA · Biology Physics Math Economics Chemistry CS Earth Science Arts History
 2  Stanford University                                   19 laureates ▓▓▓▓▓
    Stanford · Economics Physics Biology
 3  Rockefeller University                                11 laureates ▓▓▓
    New York · Biology
```

Every recorded subject shows, uncapped — the badge count is itself a reading of an institution's breadth. No apply
link on this page: at 267 rows it was noise. It stays on the subject pages, where the list is already narrowed to
what a student is looking for.

Header gains the three numbers a student actually wants, computed per country:

```
Institutions in the United States
268 institutions · 412 laureates · 74 cities
Recorded at the time of the award, not a whole career.
```

Changes this implies:

- `InstitutionCountry` (`build.py:237-242`) becomes `AffiliationCountry`, gaining `laureates: int` and `cities: int`;
  its members become `RankedAffiliation` rows carrying `city`, in-country `count`, and the existing `subjects` /
  `profile`. Falls out of step 3.
- `affiliation_country.html` rewritten against `.rank-list`; city and subject badges on a second line.
- One new CSS rule, `.rank-meta`, for that second line. `.country-tabs` becomes `.view-tabs` — the tabs are no longer
  country-only once subjects use them.

**Decided: flat ranked list, city on every row.** Grouping by city buries the recognisable names under alphabetical
headers; a student scanning for a place reads the institution name first.

---

## Subjects: `/subjects/<slug>/affiliations/`

Today `/subjects/biology/` (`subject.html`) is one long list of laureates and their prizes — good for browsing names,
useless for "which schools are strong in biology". The country pattern applies directly.

**Route.** Same shape as step 1 — the base route stays the default people view and gains a sibling. No existing URL
moves:

```
/subjects/biology/                 people, the default view + tabs      (unchanged)
/subjects/biology/affiliations/    institutions ranked for this subject (new)
```

The explicit pair `/subjects/biology/people/` + `/subjects/biology/affiliations/` with a chooser at
`/subjects/biology/` costs the same two templates, but breaks every published `/subjects/<slug>/` URL and re-creates
the F1 orphan. Not doing that.

**Data.** No new tables and no new queries. `Affiliation.subjects` already exists (`build.py:810-813`), so the reverse
index is a single pass over the affiliations built in step 3:

```python
def plan_subject_affiliations(affiliations: list[Affiliation]) -> dict[str, tuple[RankedAffiliation, ...]]:
    """Rank institutions per subject by laureates, counted within the subject rather than across the institution."""
```

For each affiliation, for each of its awards, bucket `record.high_school_subject → set(record.laureate_wikidata_qid)`.
The row's count is the size of that set — the in-subject count, not `Affiliation.count`. Same correctness rule as F3,
and the same `RankedAffiliation` row type the country pages use.

`plan_subjects` (`build.py:932-942`) takes `affiliations` as a new argument; `Subject` (`build.py:245-250`) gains
`affiliations: tuple[RankedAffiliation, ...]`. Both calls sit adjacent at `build.py:1289-1290`, so the wiring is two
lines.

**Volume per subject** (distinct institutions with a recorded affiliation):

| Subject | Institutions | Awards |
| --- | ---: | ---: |
| Biology | 563 | 1,392 |
| Physics | 234 | 516 |
| Chemistry | 146 | 260 |
| CS | 95 | 166 |
| Math | 89 | 243 |
| Economics | 38 | 99 |
| Earth Science | 29 | 40 |
| Arts | 26 | 44 |
| History | 4 | 4 |
| Lit | 1 | 1 |

Biology at 563 rows is the longest page on the site. Still one ranked list — the ranking puts what a student wants in
the first screen, and the tail is a reference, not a wall. Revisit only if the rendered page exceeds a few hundred KB.

**Template.** `subject_affiliations.html`, same `.rank-list` row as the country page, so both are one design:

```
Biology · Institutions
563 institutions · 1,392 awards recorded

 1  Harvard University                                    31 laureates ▓▓▓▓▓▓▓▓
    Cambridge, United States · How to Apply ↗
 2  MRC Laboratory of Molecular Biology                   14 laureates ▓▓▓
    Cambridge, United Kingdom · How to Apply ↗
```

Here the country **is** shown on each row — the reverse of the country page, where the country is the page and only
the city varies. Both pages carry the same "City, Country" idea; each drops the half that is already in the title.

Cross-link both directions so a student can pivot: the subject-institutions row links to the institution page, and the
country-institutions row's subject badges already link to `/subjects/<slug>/` — point them at the institutions tab
instead.

→ *verify:* an institution recorded for two subjects appears on both subject pages with a per-subject count;
`/subjects/biology/` still resolves; nav and breadcrumbs reach the new page in ≤2 clicks.

---

## Not in scope

- Pagination for large index pages — 268 and 563 rows are long but scannable, and no other index paginates except
  `/people/`.
- Country name normalization as a data migration (F6 adds a guard only).
- Filling the 40 US institutions with no recorded city, or the 170 with no `application_url`.
- The `map.html` work in the working tree.
