# Born-in and affiliation views — 20260725

Two cross-cutting views for a student audience: where laureates were **born**, and which **institutions** they were at.
Both cut across prizes, which the current prize → category → year → person structure cannot do.

Companion to `docs/specs/datasets-website-cleanup-20260725.md`. Discipline tags are a separate, larger idea and are **not**
in this spec.

## Data as it stands

Measured against `awards.sqlite3` on 20260725, 3,091 award records.

| Field | Populated | Distinct | Notes |
|---|---|---|---|
| `birth_country` | 3,048 (99%) | 171 | Historical states carry the modern country in parentheses |
| `affiliation_name` | 2,243 (73%) | 924 | 644 appear once; only 34 appear 10+ times |
| `affiliation_country` | 1,820 (59%) | — | Not used by this spec |

### Countries resolve cleanly

The data already encodes `Historical State (Modern Country)`:

```
Prussia (Germany)                          Austria-Hungary (Czech Republic)
Russian Empire (Poland)                    Union of Soviet Socialist Republics (Belarus)
West Germany (Germany)                     German-occupied Poland (Poland)
```

Taking the parenthetical collapses 171 values to 114. That name is **accurate and interesting** — a laureate born in
Prussia was born in Prussia — so it stays on the winner page. Only the grouping resolves.

About fifteen values need an explicit alias because they carry no parenthetical:

| Stored | Resolves to |
|---|---|
| `USA` (38) | United States |
| `the Netherlands` (2) | Netherlands |
| `Czechia` (1) | Czech Republic |
| `People's Republic of China` (6) | China |
| `Russian Federation` (4) | Russia |
| `USSR` (2), `Soviet Union; Russia` (1), `Russian Empire` (1) | Russia |
| `Prussia` (1) | Germany |
| `Scotland` (10) | United Kingdom |
| `Korea (South Korea)` (2) | South Korea |

### Affiliations do not resolve cleanly

The top band is split by aliasing, so raw counts would be wrong:

| Stored | Records | True institution |
|---|---|---|
| `Massachusetts Institute of Technology` | 40 | MIT — **64 combined** |
| `Massachusetts Institute of Technology (MIT)` | 24 | " |
| `Harvard University` | 61 | Harvard — **66 combined** |
| `Harvard University, USA` | 5 | " |
| `University of California` | 40 | Ambiguous: no campus named |
| `University of California, Berkeley` | 18 | A real, distinct campus |
| `Freelance` | 19 | Not an institution |

Judgement calls to settle before implementation, listed in "Open questions".

## Goals

1. `/countries/` — every birth country ranked by laureate count, and `/countries/<slug>/` per country.
2. `/affiliations/` — institutions ranked by laureate count.
3. Both state their own limits on the page. A student must not read "United States 1,129" as "American science
   produced 1,129 laureates", nor an affiliation ranking as complete when 27% of records have no affiliation.

## Non-goals

- Discipline tags. Separate spec.
- Maps, coordinates, or flags. See "Open questions".
- `affiliation_country`, at 59% coverage.
- Per-affiliation pages. The index carries the value; per-institution pages can follow if wanted.

## Counting rule

**Count laureates, not award records.** A laureate with seven awards is one person born in one country. Counting
records would rank countries by how decorated their emigrants were rather than how many laureates they produced.

```
country page count  = COUNT(DISTINCT laureate_wikidata_qid)
affiliation count   = COUNT(DISTINCT laureate_wikidata_qid)
```

Records with no `laureate_wikidata_qid` (5 rows) are excluded from both views, as they are from person pages.

## Routes

```
/countries/                      index, all birth countries by laureate count
/countries/<slug>/               one country: its laureates, each linking to their person page
/affiliations/                   index, institutions by laureate count
```

Roughly 114 country pages plus 2 index pages, taking the site from 7,122 to about 7,238.

## Data changes

Two different treatments, because the two problems are different in kind.

**Countries — resolved at build time, database untouched.** The historical name is information, not an error.
`Prussia (Germany)` continues to display on the winner page; only the grouping key resolves to `Germany`.

**Affiliations — normalized in the database**, following `CLEAN-5`. `Massachusetts Institute of Technology (MIT)`
is not information, it is the same institution written twice. A one-off script in `scripts/`, applied in a
transaction after a backup, mapping only the names that appear 10 or more times (34 of them). The 644 singletons are
left alone: they never reach a top-N view, and normalizing them needs judgement no text rule supplies.

## Files

- `website/build.py`
  - `AWARD_COLUMNS` (existing line 48) and `AwardRecord` (existing line 90) — add `birth_country` is already present;
    no schema change needed.
  - New `COUNTRY_ALIASES: dict[str, str]` constant and `resolve_country(value: str) -> str` near `slugify`
    (existing line ~200).
  - New `plan_places(...)` beside `plan_people` (existing line ~330), returning ranked country and affiliation rows.
  - `create_site_plan` (existing line ~470) — emit the new `PageJob`s next to the people pages (existing line ~690).
  - `SitePlan` (existing line ~150) — add `country_count`.
  - `TEMPLATES` (existing line 36) — add the new templates.
- `website/templates/countries.html`, `country.html`, `affiliations.html` — new.
- `website/templates/base.html`, existing lines 20-23 — extend the header nav.
- `website/static/style.css` — reuse `.highlights` and `.people-index`; add a rank-and-count row style.
- `scripts/normalize_affiliations.py` — new, one-off, dry-run by default.
- `awards.sqlite3` — `affiliation_name` for the 34 frequent names.

## Page shape

```
/countries/
  ┌──────────────────────────────────────────────┐
  │ Where laureates were born                    │
  │ 2,367 laureates · 114 countries              │
  │                                              │
  │ Born in, not where the work was done. Many   │  <- the honest note, not a footnote
  │ laureates emigrated; this counts birthplace  │
  │ only.                                        │
  │                                              │
  │  1  United States      1,129 ─────────────   │  <- reuse the homepage score-bar idea
  │  2  United Kingdom       299 ────            │
  │  3  Germany              210 ───             │
  └──────────────────────────────────────────────┘
```

`/affiliations/` mirrors it, with its own note: *"Affiliation is recorded for 2,243 of 3,091 awards (73%). Rankings
reflect what is recorded, not the full picture."*

## Acceptance

1. Every country and affiliation count matches the equivalent SQL against `awards.sqlite3`.
2. Each laureate appears exactly once per country page; no laureate appears on two country pages.
3. `USA` and `United States` produce one row, not two. `Prussia (Germany)` counts toward Germany while the winner
   page still reads `Prussia (Germany)`.
4. MIT appears once with 64, not twice with 40 and 24.
5. Every internal link resolves — the existing `dist/` crawl check stays at zero broken.
6. Every new page has a unique title and description.
7. Both index pages state their coverage limitation above the ranking, not below it.

## Open questions

Each of these changes what gets built; none should be guessed.

1. **`University of California` (40 records, no campus).** Fold into Berkeley, keep as its own umbrella row, or drop
   it from the ranking as unresolvable? Recommend: keep as its own row labelled "University of California
   (campus unspecified)" — inventing a campus would be fabrication.
2. **`Harvard Medical School` (21) vs `Harvard University` (61).** One institution or two? Recommend: two. The
   medical school is a meaningful distinction in this dataset.
3. **`Freelance` (19), and similar non-institutions.** Recommend: a small blocklist, excluded from the ranking.
4. **`Scotland` (10).** Fold into United Kingdom, or keep separate? Recommend: fold, with the winner page still
   reading Scotland.
5. **Flags.** Emoji flags do not render on Windows Chrome or Edge — students see the letters `US`. Options: no flags
   (recommended), or roughly 90 inline SVGs at about 100 KB total, which keeps the site zero-JS and self-contained.
6. **Header navigation** is currently Prizes | People. Does it become Prizes | People | Countries | Institutions
   (four items), or do both live under one "Explore" page?
