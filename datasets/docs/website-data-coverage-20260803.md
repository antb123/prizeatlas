# What's missing — data coverage on the about page — 20260803

## Goals

Publish, at the bottom of the about page, what the dataset does **not** know. Two tables — one over award records, one
over institutions — each listing a field, how many rows carry it, how many do not, and the percentage complete. A
reader who wants to contribute should be able to see the largest gap in five seconds and know it is real work, not a
rounding error.

That goal decides the sort: rows run **least complete first**, so the biggest contribution opportunity is the first
line of each table rather than something below the fold on a phone.

## Background

`datasets/docs/datasets-data-gaps-20260726.md` measured these gaps for internal use. Nothing reaches the reader. The
about page today (`datasets/website/templates/about.html:9-14`) opens with a `<dl class="totals">` of seven confident
numbers — 1,986 laureates, 2,721 awards, 628 institutions — and the rest of the page never qualifies them. A visitor
has no way to learn that 43% of records carry no ORCID, or that four institutions in five have no logo.

`AGENTS.md` requires blank over guessed, so a blank cell is an unmet research task, not an error. That makes coverage
publishable: every gap below is an invitation, and the page already asks for contributions
(`datasets/website/templates/about.html:57`).

The counting rule that makes this honest is the one the census established: a cell that the rules *require* to be
blank is not a gap. Death date is blank for 1,338 records because those laureates are alive. Category is blank for 726
because five prize families award no categories. Publishing those as "missing" would be false.

Measured against `datasets/awards.sqlite3` on 2026-08-03. The census figures are stale — it measured 3,091 records and
304 institution rows; the database now holds 2,721 records, 18 of them Organizations, and 628 institutions reach the
site.

## Assumptions

1. **Load-bearing.** A field appears in a table only if a blank means *unknown*. Fields that are legitimately blank —
   `death_*`, `category`, `prize_share`, `birth_year`, `field_language`, `biographical_note`, `remarks`,
   `affiliation_sub_name`, `source_laureate_id` — are omitted entirely, not shown with an "n/a" column. Confirmed with
   the owner 2026-08-03.
2. **Load-bearing.** Denominators differ per row and MUST be shown in the cell. Organizations carry no birth data, so
   laureate fields are measured against the 2,703 individual records; institution identity is measured against the
   2,642 records that name an institution. Using 2,721 throughout would understate every laureate gap.
3. **Load-bearing.** "Names an institution" MUST mean `_named_affiliations(record)` is non-empty
   (`datasets/website/build.py:1913-1915`), not `record.affiliation_name` being non-blank. Those differ: the site
   counts every row of `record.affiliations`, including the 94 extra rows on 66 records, and excludes
   `AFFILIATION_BLOCKLIST` (`Freelance`, 19 records). The naive column gives 2,641; the site's own model gives 2,642.
   Publishing a number the site's institution pages contradict is the one failure this section cannot afford.
4. **Load-bearing.** Every UI key MUST exist in all four catalogues. `datasets/website/build.py:846` fails the build
   when `set(language.ui) != set(english_ui)`, and `:832` requires every key a template references to exist. There is
   no English fallback.
5. **Load-bearing.** Every coverage label is a UI key. No literals, no "is it a proper noun" branch. Identifier labels
   whose value happens to be identical in all four languages (`ORCID iD`) still get a key with that value repeated —
   uniform and dull beats clever.
6. `affiliate_ror` (spelled that way in the schema and in `AwardRecord` — not `affiliation_ror`; do not "correct" it),
   `author_openalex_id` and `institution_openalex_id` are record-level columns with no counterpart on
   `AwardAffiliation`, so they cannot be measured per institution on a multi-institution record. ROR and OpenAlex
   coverage is therefore reported **only** in the institutions table. Even there it measures what the site holds, not
   what the registries hold: `plan_affiliations` reads both only from `position == 1`
   (`datasets/website/build.py:2110-2119`), so an institution that appears exclusively as a secondary affiliation
   cannot receive one. The rows are a floor and MUST be worded as such.
7. Numbers are computed at build time from data already in memory in `plan_about_page`. No new query, no new database
   read, no cache.
8. Counts drift as enrichment continues. The tables are generated, never typed; the figures below are a dated
   measurement used to design the layout, asserted in tests as a *shape*, not as constants.
9. `affiliation_city`, `affiliation_country` and `affiliation_coordinates` travel together — today all three are
   present on all 2,735 named affiliation rows — so they collapse into one "Institution location" row rather than
   three identical ones. **The published row counts records, not rows**: a record is covered only when *every*
   affiliation it names is located, giving a denominator of 2,642 records. That row is data, not an invariant: if the
   fields ever diverge it drops below 100% and says so. Incompleteness MUST NOT fail the build on the one page whose
   purpose is to publish incompleteness.

## Scope

Five files, ~170 lines added. Additive only — no semantic removals, and no existing key, route or template block is
deleted.

| File | Change | Lines |
|---|---|---:|
| `datasets/website/build.py` | `Coverage` dataclass, `_located`, two builder functions, wire into `plan_about_page`, localise in `_render_job` | ~70 |
| `datasets/website/templates/about.html` | one `<section>`, two tables | ~35 |
| `datasets/website/static/style.css` | `.coverage` table rules plus one narrow-width rule | ~19 |
| `datasets/website/i18n/{en,es,fr,ja}.toml` | 20 new keys each | ~80 |
| `datasets/tests/test_build_website.py` | coverage assertions | ~35 |

No new dependency. No route change. No sitemap change. The about page grows by roughly 1.5KB of HTML.

---

## Measured coverage

The rows the section renders, measured 2026-08-03. Reproduce with [Re-measuring](#re-measuring).

### Award records — 2,721

| Field | Recorded | Missing | Complete |
|---|---:|---:|---:|
| ORCID iD | 1,170 of 2,703 | 1,533 | 43.3% |
| Birth coordinates | 2,609 of 2,703 | 94 | 96.5% |
| Institution | 2,642 of 2,721 | 79 | 97.1% |
| Institution Wikidata ID | 2,575 of 2,642 | 67 | 97.5% |
| Citizenship | 2,652 of 2,703 | 51 | 98.1% |
| Birth city | 2,654 of 2,703 | 49 | 98.2% |
| Birth country | 2,686 of 2,703 | 17 | 99.4% |
| Birth date | 2,696 of 2,703 | 7 | 99.7% |
| Institution location | 2,642 of 2,642 | 0 | 100.0% |

"Institution" means the record names at least one institution the site will count. "Institution location" means every
institution it names carries a city, a country and coordinates — one row instead of three identical ones
(Assumption 9), and the only row currently at 100%. "Institution Wikidata ID" counts a record as covered only when
*every* institution it names is identified, which is why its denominator is 2,642 records rather than 2,735 rows.

### Institutions — 628

| Field | Recorded | Missing | Complete |
|---|---:|---:|---:|
| Logo | 130 of 628 | 498 | 20.7% |
| Description | 250 of 628 | 378 | 39.8% |
| How to apply | 251 of 628 | 377 | 40.0% |
| ROR ID | 448 of 628 | 180 | 71.3% |
| OpenAlex ID | 448 of 628 | 180 | 71.3% |
| Type | 581 of 628 | 47 | 92.5% |
| Wikidata ID | 583 of 628 | 45 | 92.8% |

The two tables tell different stories, which is why both are shown: award records are 96–100% complete on everything
except ORCID, while institution metadata is the real backlog.

**The ROR and OpenAlex rows are a floor, not a measurement.** `plan_affiliations` collects both identifiers only from
affiliations at `position == 1` (`datasets/website/build.py:2110-2119`), because they are record-level columns
(Assumption 6). An institution that appears only as somebody's second affiliation can therefore never receive one,
however well the source data is populated. 71.3% is what the *site* holds, which is the honest thing for the site to
publish, but the published wording MUST NOT imply the registries lack these institutions. `coverage.intro` carries
that caveat in one clause; the rows MUST NOT be presented as registry coverage.

---

## Design

### Data flow

```
read_database()                    plan_about_page()                     _render_job()              render
  records ──────────────┐
                        ├─► _award_coverage(records) ─────► award_coverage ─────► rows of formatted ─► about.html
create_site_plan()      │                                                          strings              two <table>
  affiliations ─────────┴─► _institution_coverage(affs) ─► institution_coverage ─┘
                               award_total / institution_total (plain ints) ─────┘
```

There is exactly **one** render path. `_render_job` (`datasets/website/build.py:4455-4485`) renders every page for
every language, and an English-only build is simply `load_languages(..., language_codes=("en",))`
(`datasets/website/build.py:888`) feeding that same function with the `en` catalogue. An earlier draft of this spec
claimed a second unlocalised path at `:4592`; that line is `render_error_page`, which renders `/404.html` and has no
about-page context.

`plan_about_page` (`datasets/website/build.py:3432-3460`) already receives both `records` and `affiliations` — it uses
`len(records)` and `len(affiliations)` for the totals block. Nothing new is passed in.

### `Coverage`

Add after `Affiliation` (`datasets/website/build.py:409-423`):

```python
@dataclass(frozen=True, slots=True)
class Coverage:
    """One field's completeness. `total` is the rows the field can apply to, which is not always every row."""
    label_key: str
    recorded: int
    total: int

    @property
    def missing(self) -> int:
        return self.total - self.recorded

    @property
    def percent(self) -> float:
        return self.recorded / self.total * 100 if self.total else 0.0
```

`total` is per row, never a table-wide constant — Assumption 2 is enforced by the type, not by a comment. The
zero guard exists for synthetic test fixtures that hold no individuals; production data never hits it.

### Builders

Two module-level functions beside `plan_about_page`, each returning rows sorted **least complete first** so the worst
gap is the first line the eye lands on:

```python
def _award_coverage(records: Sequence[AwardRecord]) -> tuple[Coverage, ...]:
    people = [record for record in records if record.laureate_type != "Organization"]
    named = [record for record in records if _named_affiliations(record)]
    counted = (
        ("fact.birth_date", sum(1 for r in people if _nonblank(r.birth_date)), len(people)),
        ("fact.birth_country", sum(1 for r in people if _nonblank(r.birth_country)), len(people)),
        ("fact.birth_city", sum(1 for r in people if _nonblank(r.birth_city)), len(people)),
        ("fact.citizenship_countries", sum(1 for r in people if _nonblank(r.citizenship_countries)), len(people)),
        ("coverage.birth_coordinates", sum(1 for r in people if _nonblank(r.birth_coordinates)), len(people)),
        ("coverage.institution", len(named), len(records)),
        ("coverage.institution_place", sum(1 for r in named if _located(r)), len(named)),
        ("coverage.institution_qid",
         sum(1 for r in named if all(_nonblank(a.wikidata_qid) for a in _named_affiliations(r))), len(named)),
        ("coverage.orcid", sum(1 for r in people if _nonblank(r.orc_id)), len(people)),
    )
    return tuple(sorted((Coverage(*row) for row in counted), key=lambda item: item.percent))
```

Sorted ascending — least complete first, per Goals.

`_located` is the one supporting predicate, and it replaces what an earlier draft made a build-stopping invariant:

```python
def _located(record: AwardRecord) -> bool:
    """Every institution this record names has a city, a country and coordinates."""
    return all(
        _nonblank(affiliation.city) and _nonblank(affiliation.country) and _nonblank(affiliation.coordinates)
        for affiliation in _named_affiliations(record)
    )
```

A page whose whole purpose is publishing what the dataset does not know MUST NOT fail the build when the dataset does
not know something. Incomplete location data is a coverage row that drops below 100%, which is exactly the signal this
section exists to send.

`_institution_coverage(affiliations)` takes the same shape, every row against `len(affiliations)`. Spelled out because
this is where the label reuse and the `None` profile are easy to get wrong:

```python
def _institution_coverage(affiliations: Sequence[Affiliation]) -> tuple[Coverage, ...]:
    total = len(affiliations)
    profiles = [item.profile for item in affiliations]
    counted = (
        ("coverage.wikidata_id", sum(1 for item in affiliations if _nonblank(item.qid)), total),
        ("coverage.ror_id", sum(1 for item in affiliations if _nonblank(item.ror)), total),
        ("coverage.openalex_id", sum(1 for item in affiliations if _nonblank(item.openalex_id)), total),
        ("coverage.kind", sum(1 for p in profiles if p and _nonblank(p.kind)), total),
        ("common.how_to_apply", sum(1 for p in profiles if p and _nonblank(p.application_url)), total),
        ("coverage.description", sum(1 for p in profiles if p and _nonblank(p.description)), total),
        ("coverage.logo", sum(1 for p in profiles if p and _nonblank(p.logo_url)), total),
    )
    return tuple(sorted((Coverage(*row) for row in counted), key=lambda item: item.percent))
```

`Affiliation.profile` is `AffiliationProfile | None` (`datasets/website/build.py:420`); a `None` profile counts as
missing on all four profile rows, which is why `p and …` guards each. `common.how_to_apply` is the existing reviewed
key, reused rather than duplicated.

Wire the coverage rows and the two plain-int totals into the `_page(...)` call at
`datasets/website/build.py:3451-3459`, after `totals=`:

```python
        award_coverage=_award_coverage(records),
        institution_coverage=_institution_coverage(affiliations),
        award_total=len(records),
        institution_total=len(affiliations),
```

`award_total` and `institution_total` are plain ints on the context — the counts, not the sequences. `_render_job`
formats them; the template interpolates them into the captions.

### Localisation

Numbers MUST be formatted per language, following the `totals` precedent that already rewrites a context tuple
(`datasets/website/build.py:4480-4485`). Add beside it a helper both render paths call:

```python
def _localized_coverage(language: Language, rows: Sequence[Coverage]) -> tuple[tuple[str, ...], ...]:
    return tuple(
        (
            language.text(row.label_key),
            language.text("coverage.of", recorded=format_number(row.recorded, language),
                          total=format_number(row.total, language)),
            format_number(row.missing, language),
            format_number(row.percent, language, 1),
        )
        for row in rows
    )
```

The `{recorded} of {total}` string is assembled here, not in the template, because word order differs by language and
the template must not concatenate. Labels resolve here too — with Assumption 5 there is no branch, every label is a
key.

Call it in `_render_job` immediately after the existing `totals` block (`datasets/website/build.py:4480-4485`), which
is the precedent this follows exactly:

```python
    for key in ("award_coverage", "institution_coverage"):
        if rows := context.get(key):
            context[key] = _localized_coverage(language, rows)
    for key in ("award_total", "institution_total"):
        if (value := context.get(key)) is not None:
            context[key] = format_number(value, language)
```

One insertion covers every language including an English-only build, because `_render_job` is the only render path.

### Template

Append one section to `datasets/website/templates/about.html`, after the prizes section closes at line 60 and before
`{% endblock %}`:

```html
<section>
  <h2>{{ t("coverage.heading") }}</h2>
  <p>{{ t("coverage.intro") }}</p>
  {% for caption, rows in [
       (t("coverage.awards_caption", total=award_total), award_coverage),
       (t("coverage.institutions_caption", total=institution_total), institution_coverage)] %}
  <table class="coverage">
    <caption>{{ caption }}</caption>
    <thead>
      <tr>
        <th scope="col">{{ t("coverage.field") }}</th>
        <th scope="col">{{ t("coverage.recorded") }}</th>
        <th scope="col">{{ t("coverage.missing") }}</th>
        <th scope="col">{{ t("coverage.complete") }}</th>
      </tr>
    </thead>
    <tbody>
      {% for label, recorded, missing, percent in rows %}
      <tr>
        <th scope="row">{{ label }}</th>
        <td>{{ recorded }}</td>
        <td>{{ missing }}</td>
        <td>{{ percent }}%</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% endfor %}
</section>
```

`<caption>` carries the denominator sentence and `<th scope="row">` the field name — the accessible structure comes
free from base HTML, as elsewhere on the site (`datasets/website/templates/winners.html:11-25`).

### Style

The site ships **no table CSS at all** — `datasets/website/static/style.css` holds one table selector (line 27, a
Japanese font override for `.explorer`); tables render at browser default. Add the minimum for four numeric columns,
near the `.award-logo` block (`datasets/website/static/style.css:278-295`):

```css
.coverage { width: 100%; border-collapse: collapse; margin-block: 1rem; font-size: 0.85rem; }
.coverage caption { text-align: left; padding-block: 0.5rem; font-weight: 600; }
.coverage th, .coverage td { padding: 0.35rem 0.4rem; border-bottom: 1px solid var(--rule); }
.coverage thead th { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.04em; }
.coverage th { text-align: left; font-weight: 400; }
.coverage td { text-align: right; font-variant-numeric: tabular-nums; }

@media (max-width: 26rem) {
  .coverage th:nth-child(3), .coverage td:nth-child(3) { display: none; }
}
```

`tabular-nums` is the one thing that matters visually: without it the digits do not align and the table reads as a
list. No bars, no gradients, no JavaScript — the audience is low-end phones on metered data, and this section MUST NOT
add measurable page weight.

The media query is Requirement 4's fix, written now rather than left to the implementer: below 416px the `Missing`
column is hidden. It is the right column to drop because it is derivable — `Recorded` already reads "1,170 of 2,703",
so the reader loses nothing but a subtraction. German- and Japanese-length headers are the binding constraint, and
`Missing` is dropped in every language rather than conditionally, so the four catalogues cannot diverge in layout.

### New keys

**20 new `coverage.*` keys per catalogue** (80 lines across the four files), plus **5 existing keys reused, separately
and unchanged**: `fact.birth_date`, `fact.birth_country`, `fact.birth_city`, `fact.citizenship_countries` for four
laureate rows and `common.how_to_apply` for the application-URL row.

The two sets do not overlap and MUST NOT be merged. There MUST NOT be a `coverage.birth_date` or a
`coverage.how_to_apply` — every key in the table below begins `coverage.` and none of them duplicates a reused key.

| Key | English |
|---|---|
| `coverage.heading` | What's missing |
| `coverage.intro` | Every blank below is an unrecorded fact, not a zero — this project leaves a cell empty rather than guess. These are the gaps, and contributions that close them are welcome. |
| `coverage.awards_caption` | Award records — {total} |
| `coverage.institutions_caption` | Institutions — {total} |
| `coverage.field` | Field |
| `coverage.recorded` | Recorded |
| `coverage.missing` | Missing |
| `coverage.complete` | Complete |
| `coverage.of` | {recorded} of {total} |
| `coverage.birth_coordinates` | Birth coordinates |
| `coverage.institution` | Institution |
| `coverage.institution_place` | Institution location |
| `coverage.institution_qid` | Institution Wikidata ID |
| `coverage.orcid` | ORCID iD |
| `coverage.wikidata_id` | Wikidata ID |
| `coverage.ror_id` | ROR ID |
| `coverage.openalex_id` | OpenAlex ID |
| `coverage.kind` | Type |
| `coverage.description` | Description |
| `coverage.logo` | Logo |

The implementer MUST verify the four catalogues hold identical key sets before committing — `build.py:846` is the
check that will otherwise fail the build.

Placeholders MUST be identical across catalogues (`datasets/website/build.py:854`). New keys MUST NOT be added to any
catalogue's `reviewed` list until a speaker has checked them.

---

## Behavior / Acceptance

### Requirement 1: Denominators — each field MUST be measured against the rows it can apply to

#### Scenario: a laureate field on an organization's record
- WHEN a record has `laureate_type = "Organization"`
- THEN it MUST NOT be counted in the total for any birth, citizenship or ORCID row
- AND the birth-date row MUST report a total of 2,703, not 2,721

#### Scenario: institution identity on a record naming no institution
- WHEN `_named_affiliations(record)` is empty
- THEN the record MUST NOT be counted in the total for the Institution Wikidata ID row
- AND that row MUST report a total of 2,642

#### Scenario: a record naming several institutions
- WHEN a record has two named affiliations and only one carries a Wikidata QID
- THEN the record MUST count as *not* covered for Institution Wikidata ID

#### Scenario: a blocklisted affiliation
- WHEN a record's only affiliation name is `Freelance`
- THEN it MUST count as having no institution, matching what the site's institution pages show

### Requirement 2: `_render_job` MUST format every coverage number

#### Scenario: the multilingual build
- WHEN the site is built for `fr`
- THEN the `/fr/` about page MUST show the French group separator in the coverage cells
- AND MUST NOT contain the substring `Coverage(`

#### Scenario: the English-only build
- WHEN the site is built with `language_codes=("en",)`
- THEN the about page MUST show `2,696 of 2,703`
- AND MUST NOT contain the substring `Coverage(`

#### Scenario: the caption total
- WHEN either table renders
- THEN its `<caption>` MUST carry the group-separated total for that language, never a bare `2721`

### Requirement 3: Incomplete data MUST become a number, never a build failure

#### Scenario: affiliation sub-fields diverge
- WHEN a record names two institutions and one has blank `coordinates`
- THEN the build MUST succeed
- AND that record MUST count as not covered in the Institution location row, dropping it below 100%
- AND a unit test MUST construct such a record and assert both, so the row cannot silently report 100% forever

#### Scenario: reused labels
- WHEN the awards table renders
- THEN the birth rows MUST show the values of `fact.birth_date`, `fact.birth_country`, `fact.birth_city` and
  `fact.citizenship_countries`, and the institutions table MUST show `common.how_to_apply`
- AND a test MUST assert those five reused labels appear, since a wrong `label_key` fails no other check

### Requirement 4: Layout MUST survive a 320px viewport

#### Scenario: the narrowest common phone
- WHEN the about page is rendered at 320px CSS width in any of the four languages
- THEN the `Missing` column MUST be hidden by the `max-width: 26rem` rule
- AND the document body MUST NOT scroll horizontally

The repo has no browser-driven test harness, and this spec MUST NOT add one for a single media query. The check
splits:

- a unit test asserts the `max-width: 26rem` block is present in the built `static/style.css`;
- the implementer opens the four built about pages at a 320px viewport and records, in the implementation handoff,
  the exact paths checked and the browser used. The routes are localised, so read them from the build rather than
  assuming: `dist/about/`, `dist/es/…`, `dist/fr/…`, `dist/ja/…`, whose segments come from each catalogue's
  `segments.about`.

A unit test alone is weak evidence for a layout claim and MUST NOT be reported as verifying it.

### Requirement 5: Rows MUST be ordered least complete first

#### Scenario: the first data row
- WHEN the awards table renders against current data
- THEN its first body row MUST be the ORCID row, the largest gap
- AND the institutions table's first body row MUST be the Logo row

### Requirement 6: The section MUST be last

#### Scenario: reading order
- WHEN the about page renders
- THEN the coverage section MUST follow the prizes/contributions section
- AND the totals block at the top MUST be unchanged

---

## Re-measuring

Laureate fields, against individuals only:

```sql
SELECT count(*) FROM awards WHERE laureate_type <> 'Organization';
SELECT count(*) FROM awards WHERE laureate_type <> 'Organization' AND trim(coalesce(birth_city,'')) <> '';
```

The institution figures MUST NOT be taken from SQL. `_named_affiliations()`
(`datasets/website/build.py:1913-1915`) merges `awards` with `award_extra_affiliations` and applies
`AFFILIATION_BLOCKLIST`; the naive query below returns 2,641 where the site's model returns 2,642, and that one-record
gap is exactly the bug this spec exists to avoid. Assert institution numbers in the test suite, through the build.

```sql
-- WRONG for this purpose; shown so nobody re-derives it
SELECT count(*) FROM awards WHERE trim(coalesce(affiliation_name,'')) <> '';
```

Institution metadata is measured over the 628 institutions the site builds, not the 643 rows in `affiliations` — 15
rows are unreferenced. Reachable only through `plan_affiliations()` (`datasets/website/build.py:3502`).

The Institution location row, over the primary column only — the extra rows live in `award_extra_affiliations` and
only `_located()` sees both:

```sql
SELECT count(*) FROM awards WHERE trim(coalesce(affiliation_name,'')) <> ''
  AND (trim(coalesce(affiliation_city,'')) = '' OR trim(coalesce(affiliation_country,'')) = ''
       OR trim(coalesce(affiliation_coordinates,'')) = '');
```

Currently 0, which is why the row reads 100%. A non-zero result is a coverage number, not a defect in this section.

---

## Out of scope

- Fixing any gap. This publishes the numbers; the census
  (`datasets/docs/datasets-data-gaps-20260726.md`) prioritises the work.
- Per-prize or per-country coverage breakdowns.
- A machine-readable coverage endpoint. The CSV download already exposes the raw data.
- Refreshing the stale census document against the current 2,721-record database.
