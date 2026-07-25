# Awards website cleanup — 20260725

Cleanup spec for the static site in `website/`. Four goals, in priority order:
**stay** (first impression) → **found** (SEO) → **usable** (navigation) → **beautiful** (craft).

Reviewed against the rendered site at `http://localhost:8000/` (headless Chrome, desktop 1440px and mobile 390px).

## Current state

| | |
|---|---|
| Pages | 4,858 (`dist/`, 40 MB, zero JavaScript) |
| Templates | `base.html`, `index.html`, `prize.html`, `category.html`, `year.html`, `winner.html` |
| Stylesheet | `static/style.css`, 353 lines |
| Builder | `build.py`, ~800 lines |
| Data | `awards.sqlite3` — 3,091 awards, 2,381 distinct laureates, 14 prizes, 1901–2026, 172 birth countries |

Data present in the DB but **not surfaced anywhere on the site**:

| Column | Populated | Used |
|---|---|---|
| `birth_coordinates` | 3,013 / 3,091 | no |
| `sex` | 3,048 | no |
| `death_date` | 1,672 | no |
| `birth_country` | 3,048 | facts sidebar only |
| `affiliation_coordinates` | 319 | no |
| `laureate_wikidata_qid` | 3,086 | no (links go to a Wikipedia *search*) |

479 laureates hold more than one award. Nothing on the site connects them.

---

## 1. First impression — get people to stay

**Diagnosis.** The homepage is a header, 14 ranked prize names with blurbs and scores, and a footer
(`templates/index.html`, 25 lines). A visitor learns that 14 prizes exist and nothing about the 2,381
people behind them. There are no names, no numbers, no dates, no way in. The strongest content the
dataset holds — that Shinya Yamanaka won 7 major prizes and Sydney Brenner 6 — is invisible.

### 1.1 Add a scale line above the ranking
`templates/index.html` after line 7.

```
2,381 laureates · 3,091 awards · 14 prizes · 1901–2026 · 172 countries
```

Communicates "this is a database" in one line. Counts computed in `build.py` `create_site_plan()`
(line 266) and passed into the index context (line ~323).

### 1.2 Add "Most decorated" — the hook
`templates/index.html`, new section above the ranking `<ol>` (line 8).

Top ~8 laureates by award count, from `GROUP BY laureate_wikidata_qid HAVING COUNT(*) > 1`:

| Laureate | Awards | Prizes |
|---|---|---|
| Shinya Yamanaka | 7 | Nobel, Lasker, Wolf, Kyoto, Shaw, Gairdner, Breakthrough |
| Sydney Brenner | 6 | Nobel, Lasker, Kyoto, Gairdner |
| Frederick Sanger | 5 | Nobel, Lasker, Gairdner |
| Simon Donaldson | 5 | Fields, Breakthrough, Crafoord, Shaw, Wolf |

No other site shows this. It is the single best reason to stay. Depends on §3.1 (person pages) for link targets.

### 1.3 Add "Recently awarded"
`templates/index.html`, new section. 2025–2026 laureates with names and prize. Names are concrete;
prize names are abstract. Gives the homepage a reason to be revisited.

### 1.4 Give the score a visual scale
`templates/index.html` line 20, `static/style.css` `.score` (lines 185–195).

Currently `SCORE 100` and `SCORE 66` are right-aligned text in a 7rem column — the reader must compare
numerals. Add a thin bar (`width: calc(var(--score) * 1%)`, CSS custom property set inline). No images,
no JS.

---

## 2. SEO — get people to find it

**Diagnosis.** Titles are reasonable; everything else is missing or templated to the point of being a
thin-content signal.

### 2.1 Meta descriptions are 4,858 variations of one sentence
`build.py` — description strings are generated per page type.

Current:
```
"Meet the Nobel Prize for Physics winners in 2024."
"Meet the Max Planck Medal winners in 1955."
"Geoffrey Hinton, winner of the Nobel Prize for Physics in 2024."
```

Fix: fold real data into the description — laureate names on year pages, motivation excerpt and
affiliation on winner pages, year range and laureate count on category pages.

### 2.2 Winner page titles bury the name
`build.py`, winner title construction.

Current: `Nobel Prize for Physics 2024 — Geoffrey Hinton`
Proposed: `Geoffrey Hinton — Nobel Prize for Physics, 2024`

People search for the person, not the prize. Name-first matches query intent and survives SERP truncation.

### 2.3 No Open Graph, no Twitter card
`templates/base.html`, head block (lines 3–11).

Add `og:title`, `og:description`, `og:type`, `og:url`, `og:site_name`, `twitter:card`. Without these,
every share of every page renders as a bare URL.

### 2.4 No structured data
`templates/base.html` (new block) and `templates/winner.html`.

`schema.org/Person` with the `award` property fits this dataset exactly. Emit JSON-LD on winner pages
using `full_name`, `birth_date`, `birth_place`, `sameAs` (Wikidata QID URL), and `award`. Emit
`BreadcrumbList` from the existing `breadcrumbs` context (`base.html` lines 17–27) on every page.

### 2.5 Missing `robots.txt` and `404.html`
`dist/` contains only `index.html`, `sitemap.xml`, `favicon.svg` at root. Add both;
`robots.txt` must reference the sitemap.

### 2.6 Duplicate URLs from unnormalized categories
`awards.sqlite3` → `dist/japan-prize/`.

73 Japan Prize category pages, nearly all with a single laureate, including near-duplicate slugs:

```
life-science                              /  life-sciences
medical-science-and-medicinal-science     /  medical-science-medicinal-science
electronics-information-and-communication /  electronics-information-and-communication-2
biological-production-and-environment     /  biological-production-and-biological-environment
                                          /  biological-production-ecology
                                          /  biological-production-ecology-environment
```

Two fixes, both needed:
1. Normalize `awards.category` for Japan Prize in the DB.
2. Route rotating-topic prizes (Japan, Crafoord) by **year**, not category — `build.py`
   `create_site_plan()` line ~335, `routed_categories = len(categories) > 1`. The condition needs a
   per-prize override, not a count.

---

## 3. Usability — navigation

**Diagnosis.** With 4,858 pages, no search, and no index, the only way to reach a person is to guess
their prize, then category, then year. Pages dead-end.

### 3.1 Person pages — `/people/<slug>/`
New template `templates/person.html`, new route in `build.py` `create_site_plan()`.

Key on `laureate_wikidata_qid` (3,086 / 3,091 rows). One page per laureate listing every award
chronologically. Link from every winner page and from §1.2.

**Blocked on** the name/QID correctness work being handled separately — this route merges records by
QID, so a wrong QID silently merges two people or splits one. Build the template and route first;
generate against the corrected data.

This is the highest-leverage change in the spec: it fixes retention (§1), adds 2,381 genuinely unique
indexable pages (§2), and makes the dataset navigable (§3).

```
/people/shinya-yamanaka/
  ├── Nobel Prize, Medicine, 2012      → /nobel-prize/medicine/2012/shinya-yamanaka/
  ├── Breakthrough Prize, Life Sciences, 2013
  ├── Wolf Prize, Medicine, 2011
  └── … 4 more
```

### 3.2 A–Z laureate index — `/people/`
Paginated, alphabetical, no JavaScript. The only current entry point is the 14-item homepage ranking.

*Optional, if one small script is acceptable:* client-side search over a name→route JSON index
(~250 KB for 2,381 names).

### 3.3 Winner pages dead-end
`templates/winner.html` — ends after the award `<dl>` (lines 22–28) and facts aside (lines 31–40).

Add: co-laureates for that prize/category/year, previous/next year links, and a link to the person page.
Only 343 / 3,091 records have a `biographical_note`, so most winner pages have no prose at all — these
links are the page's substance.

### 3.4 Shared motivations repeat under every name
`templates/category.html` lines 14–21.

598 award groups share a motivation across laureates; the template prints it once per person. Nobel
Physics 2024 shows the identical sentence twice, 2023 and 2025 three times each. Group recipients under
one motivation.

### 3.5 The Nobel prize page is 141 KB
`templates/prize.html` lines 40–49.

Dumps ~1,000 laureates in a two-column list under a `<details>`. The category links (lines 30–39) that
people actually want are above it but visually minor. Cap the "Winners" section at recent years and
promote the category/year entry points.

Largest pages today:

```
141 KB  nobel-prize/
 96 KB  lasker-award/
 70 KB  nobel-prize/physics/
 65 KB  nobel-prize/medicine/
```

### 3.6 No navigation in the header
`templates/base.html` lines 13–16 — the only link on 4,858 pages is the "Awards" wordmark. Add
Prizes / People / About.

---

## 4. Beauty

The typography is already good — warm paper palette, restrained editorial rhythm, correct
`focus-visible` handling. These are corrections, not a redesign. **Do not restyle what works.**

### 4.1 `h1` is oversized
`static/style.css` line 120 — `font-size: clamp(2rem, 8vw, 4.5rem)`.

72 px at desktop. On `/nobel-prize/physics/2024/geoffrey-hinton/` the title wraps to two lines and
outweighs the data it labels, pushing the facts sidebar down. Reduce the cap to ~3rem; keep the fluid
clamp for mobile.

### 4.2 Short pages leave the footer floating
`static/style.css` line 96 — `main { padding-block: 2.5rem 5rem }`.

A two-recipient year page (`/nobel-prize/physics/2024/`) renders ~700 px of content followed by empty
viewport. Add `body { min-height: 100vh; display: flex; flex-direction: column }` with
`main { flex: 1 }` so the footer sits at the bottom.

### 4.3 Year column loses its anchor
`static/style.css` lines 227–233 — `.category-years > li` uses a 6rem left column for the year.

When a year holds 3 recipients with long motivations, the row is ~200 px tall and the year label floats
alone at the top. Make it `position: sticky` within the row, or move it inline as a heading.

### 4.4 No dark mode
`static/style.css` line 2 — `color-scheme: light` is hard-locked.

The palette (lines 3–8) is already six variables. Add a `@media (prefers-color-scheme: dark)` block
overriding them.

### 4.5 Motivation text is the same weight as everything else
`static/style.css` lines 244–247. On category pages the motivation is the dominant text by volume but
reads as flat grey body copy. Italic or a smaller measure would let the names carry the page.

---

## Suggested order

1. §3.1 person pages + §3.2 index — unlocks §1.2, and is most of the SEO win
2. §3.5, §3.6, §3.3 — the listing pages people actually land on
3. §1.1–§1.4 — homepage
4. §2.1–§2.5 — metadata pass, mechanical
5. §2.6 — category normalization (touches the DB, not just the site)
6. §4 — craft pass last, once layouts have stopped moving

## Out of scope

- **Name / Wikidata QID correctness.** Known, tracked separately. Includes the winner-page
  "Find X on Wikipedia" search link (`templates/winner.html` line 9, `build.py`
  `wikipedia_search_url()` line 174) — leave it as a search URL until QIDs are trustworthy, then
  switch to direct links. §3.1 depends on this landing first.
- **Geographic and demographic pages.** `birth_coordinates` (97% populated), `sex` (3,048),
  `death_date` (1,672) are unused but that is a feature, not cleanup.
  See `docs/datasets-umap-winner-locations-20260725.md`.
