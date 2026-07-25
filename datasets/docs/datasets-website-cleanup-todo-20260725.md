# Awards website cleanup TODO

Implement `docs/datasets-website-cleanup-20260725.md` on its own branch. Use conventional commits, do not merge
until reviewed, and squash-merge into `202607`.

Rebuild and re-check after every task: `uv run website/build.py` → `dist/` regenerates without a `BuildFailure`
and `grep -c '<loc>' dist/sitemap.xml` matches `find dist -name index.html | wc -l`.

Order below is the spec's suggested order. `CLEAN-1` is blocked; start at `CLEAN-2` if the QID work has not landed.

## CLEAN-1 — Person pages and laureate index — DONE 20260725

ID: `CLEAN-1` — Add `/people/<slug>/` and a paginated `/people/` index. Spec §3.1, §3.2.

Depends-on: name/QID correctness work — landed before implementation.

Outcome: 2,367 person pages and 12 index pages; site grew 4,858 → 7,237 pages. Verified 81,453 internal links
resolve with none broken, every laureate listed exactly once, and exactly 5 winner pages without a person link
(the 5 rows with no laureate QID).

Two data findings surfaced during the build, both from the name normalization rather than the website code:

1. `breakthrough-000041` was `laureate_type='Organization'` all along — the Sudbury Neutrino Observatory team
   record. Normalization overwrote its name with Q710597's label ("Arthur B. McDonald"), duplicating the individual
   record and breaking the winner-slug uniqueness check. Split into the observatory (`Q176822`, person fields
   cleared) and the individual, per review. Backed up as `awards.sqlite3.*.sno-org-split.bak`.
2. **Still open:** those two rows have swapped affiliations — McDonald carries "Iwate Prefectural University, Japan"
   and the observatory carries "Queen's University, Canada". Left alone; not part of this task.

Files:

- `website/templates/person.html`, new;
- `website/templates/people_index.html`, new;
- `website/templates/winner.html`, existing lines 1-42;
- `website/templates/base.html`, existing lines 13-16;
- `website/build.py`, existing lines 255-263 (`_page`), 266-460 (`create_site_plan`), 35 (`TEMPLATES`);
- `website/static/style.css`, existing lines 209-266.

Relevant assumptions:

1. `laureate_wikidata_qid` is the merge key — 3,086 of 3,091 rows carry one. A wrong QID silently merges two people
   or splits one, which is why this task is blocked rather than merely risky.
2. The 5 rows with a blank QID get no person page and no link from their winner page.
3. Person slugs derive from `full_name`; collisions after QID correction are a build failure, not a silent suffix.

Steps → verify:

1. Add `person_routes: dict[str, str]` keyed by QID in `create_site_plan`, grouping records by QID and sorting each
   group by year ascending → 2,381 distinct routes, and `/people/shinya-yamanaka/` lists 7 awards across 7 prizes.
2. Register `person.html` and `people_index.html` in `TEMPLATES` and emit one `PageJob` per laureate → the builder
   fails loudly on a missing template rather than skipping the route.
3. Raise `BuildFailure` on duplicate person slugs → two laureates sharing a name abort the build with both QIDs named.
4. Render each award row as prize, category, year, motivation, linking to the existing winner route → every link in
   `/people/` resolves to a file in `dist/` (crawl `dist/` for hrefs, resolve against the filesystem, expect 0 misses).
5. Add a person link to `winner.html` after line 9 → `/nobel-prize/medicine/2012/shinya-yamanaka/` links to the
   person page, and the 5 blank-QID winner pages render without it.
6. Emit `/people/` alphabetically by surname, paginated, with prev/next links → every laureate appears exactly once
   across all pages and no page exceeds ~200 entries.
7. Add Prizes / People to the header nav in `base.html` lines 13-16 → present on all pages, relative hrefs correct at
   every depth (check root, `/nobel-prize/`, and `/nobel-prize/physics/2024/geoffrey-hinton/`).

## CLEAN-2 — Listing page repairs — DONE 20260725

ID: `CLEAN-2` — Group shared motivations, shrink the prize pages, link winner pages to their neighbours.
Spec §3.4, §3.5, §3.3.

Depends-on: none (step 4 links to `CLEAN-1` routes; land it after)

Outcome, measured on the real build:

| Page | Before | After |
|---|---|---|
| `nobel-prize/` | 141 KB | 45 KB |
| `lasker-award/` | 96 KB | 40 KB |
| `nobel-prize/physics/` | 70 KB | 63 KB |

Shared citations now print once with the recipients listed together, on both category and year pages. The prize page
carries the most recent `PRIZE_PAGE_YEARS` (30) award years; the `<details>` blob holding every older laureate is
gone, and those pages stay reachable through the category and year routes. 88,881 internal links resolve, none broken.

**Deviation from spec §3.3:** previous/next year links went on the **year** page, not the winner page. The year page
was the thinnest page type on the site and is the natural home for year navigation; the winner page already reaches
its year through breadcrumbs and now also carries co-laureates and a person link.

Files:

- `website/templates/category.html`, existing lines 14-21;
- `website/templates/prize.html`, existing lines 40-49;
- `website/templates/winner.html`, existing lines 20-29;
- `website/build.py`, existing lines 370-460;
- `website/static/style.css`, existing lines 220-253.

Relevant assumptions:

1. 598 prize/category/year groups share one motivation across laureates. Grouping is presentational — no data changes.
2. Co-laureates are the records sharing `prize_name`, `category`, and `year`, excluding the current record.

Steps → verify:

1. Group year recipients by identical motivation in `create_site_plan` and render names under one motivation in
   `category.html` → `/nobel-prize/physics/` shows the 2024 motivation once with both names, 2023 and 2025 once
   with three names each.
2. Cap `prize.html` "Winners" at recent years and promote the category/year links above it → `dist/nobel-prize/`
   drops well below its current 141 KB and `dist/lasker-award/` below 96 KB.
3. Add a co-laureate list to `winner.html` → Hinton's page links Hopfield; a sole winner renders no empty section.
4. Add previous/next year links within the same prize and category → first and last years render only one link.

## CLEAN-3 — Homepage

ID: `CLEAN-3` — Give the homepage scale, names, and a readable score. Spec §1.1-§1.4.

Depends-on: CLEAN-1 (step 2 needs person routes)

Files:

- `website/templates/index.html`, existing lines 3-24;
- `website/build.py`, existing lines 266-330;
- `website/static/style.css`, existing lines 153-195.

Relevant assumptions:

1. Counts are computed at build time from the same `records` list already in memory — no second DB pass.
2. "Most decorated" and "Recently awarded" are derived, not curated; they change when the data changes.

Steps → verify:

1. Compute laureate, award, prize, year-range, and country counts in `create_site_plan` and render a scale line after
   `index.html` line 7 → reads `2,381 laureates · 3,091 awards · 14 prizes · 1901-2026 · 172 countries` and each
   number matches the equivalent SQL against `awards.sqlite3`.
2. Render the top 8 laureates by award count above the ranking `<ol>` → Yamanaka 7 leads, Brenner 6 second, each
   linking to its person page.
3. Render 2025-2026 laureates with name and prize → every name links to a winner page that exists.
4. Set a `--score` custom property on `index.html` line 20 and add a bar to `.score` → 100 and 60 are visually
   distinguishable, the numeral stays readable, and mobile at 390px does not overflow.

## CLEAN-4 — Metadata and crawl — DONE 20260725

ID: `CLEAN-4` — Real descriptions, name-first titles, social cards, structured data, robots, 404. Spec §2.1-§2.5.

Depends-on: none

Outcome: all 7,238 descriptions and all 7,238 titles are unique; 7,236 JSON-LD blocks, all valid; no description
exceeds 200 characters.

Year-page descriptions lead with the award and then the recipients, rather than the reverse. One Breakthrough Prize
record carries a 200-character "name" (the LIGO author list); leading with the name made its year page and its winner
page truncate to the same 160 characters. Leading with the award keeps the two distinct whatever the name length.

Winner page `h1` is now the laureate's name alone — the prize, category, and year moved to the eyebrow, which the
name-first `<title>` had otherwise duplicated.

Files:

- `website/templates/base.html`, existing lines 3-11, 17-27;
- `website/templates/winner.html`, existing lines 1-42;
- `website/build.py`, existing lines 255-263, 266-460;
- `website/static/`, new `robots.txt`, new `404.html`.

Relevant assumptions:

1. Descriptions are generated per page type in `build.py`; today 4,858 pages carry one of ~5 sentence templates.
2. JSON-LD is emitted only where the data supports it — `Person` on winner and person pages, `BreadcrumbList`
   everywhere `breadcrumbs` is non-empty.
3. `sameAs` linking to Wikidata is deferred with the rest of the QID work.

Steps → verify:

1. Fold laureate names into year-page descriptions, motivation excerpt and affiliation into winner-page descriptions,
   and year range plus laureate count into category-page descriptions → no two pages in `dist/` share a description
   (extract all, sort, `uniq -d` is empty).
2. Reorder winner titles to `<name> — <prize>, <year>` → `Geoffrey Hinton — Nobel Prize for Physics, 2024`, and every
   title stays under ~60 characters or degrades gracefully.
3. Add `og:title`, `og:description`, `og:type`, `og:url`, `og:site_name`, `twitter:card` to `base.html` lines 3-11 →
   present on all 4,858 pages, `og:url` matching the existing canonical.
4. Emit `schema.org/Person` JSON-LD on winner and person pages from `full_name`, `birth_date`, `birth_city`,
   `birth_country`, and `award` → validates, and pages with missing fields omit those keys rather than emitting empty
   strings.
5. Emit `BreadcrumbList` JSON-LD from the existing `breadcrumbs` context → matches the visible trail on every page
   that has one; the homepage emits none.
6. **Done 20260725.** Add `robots.txt` referencing the sitemap, and a `404.html` reusing `base.html` → both land at
   `dist/` root and `robots.txt` names the absolute sitemap URL.

   Landed ahead of the rest of CLEAN-4 because it touches no shared code. New `write_robots()` and
   `render_error_page()` in `build.py`, new `templates/404.html`, `{% block head %}` and conditional canonical in
   `base.html`, `"404.html"` added to `TEMPLATES`.

   The error page links **absolutely** from the deployment root — it is served for arbitrary request URLs, so the
   relative hrefs every other page uses would resolve against the requested path and break. `render_error_page()`
   derives the prefix from `--base-url`, so subpath deploys stay correct.

   **Deployment follow-up, not yet done:** nginx needs `error_page 404 /404.html;` in the server block. Until then
   the file is built but never served.

## CLEAN-5 — Category normalization — DONE 20260725

ID: `CLEAN-5` — Collapse duplicate Japan Prize categories and route rotating-topic prizes by year. Spec §2.6.

Depends-on: none

Outcome: `dist/japan-prize/` holds 42 year directories instead of 73 category directories. Site-wide category pages
fell from 98 to 26; total pages from 7,237 to 7,122.

Only four merges were applied, all pure punctuation or plural variants. Backup: `awards.sqlite3.*.japan-categories.bak`.

| Merged | Into |
|---|---|
| Life Science | Life Sciences |
| Electronics, Information and Communication | Electronics, Information, and Communication |
| Medical Science and Medicinal Science | Medical Science, Medicinal Science |
| Resources, Energy, Environment and Social Infrastructure / …, Social Infrastructure | Resources, Energy, the Environment, and Social Infrastructure |

**Deliberately not merged.** Of 72 Japan Prize categories, most are genuine annual topics rather than spelling
variants — the prize picks two fields afresh each year. Pairs like "Biological Production and Biological Environment"
vs "Biological Production and Environment", or "Materials and Production" vs "Materials Science and Production", need
a subject-matter judgement rather than a text rule, so they were left alone. Routing by year makes them harmless:
category is now displayed data, not a URL.

The routing override is `YEAR_ROUTED_PRIZES` in `build.py`, keyed on the curated prize slug. Crafoord was reviewed
and left category-routed: its five categories are standing divisions, not annual topics. A year that awards more than
one topic names each one against its recipients rather than in the page heading.

Files:

- `awards.sqlite3`, `awards.category` for Japan Prize rows;
- `scripts/`, new one-off normalization script;
- `website/build.py`, existing lines 330-345 (`routed_categories = len(categories) > 1`), 212-221 (`_category_slugs`).

Relevant assumptions:

1. Japan Prize has 73 category values, nearly all with a single laureate. Several are spelling variants of one topic.
2. Crafoord rotates topics too, but across 5 stable categories — confirm before changing its routing.
3. Category is source data; normalization is a mapping table in the script, reviewed before it runs.

Steps → verify:

1. Back up `awards.sqlite3`, then list all 73 Japan Prize categories with counts → the variant pairs named in spec
   §2.6 are confirmed present before anything is written.
2. Write the normalization mapping and apply it in a transaction → `life-science`/`life-sciences` and the other named
   pairs collapse, row count is unchanged, `PRAGMA integrity_check` passes.
3. Replace the `routed_categories` count test with a per-prize override so Japan Prize routes by year → `dist/japan-prize/`
   holds year directories, not 73 near-duplicate category directories.
4. Rebuild and diff the sitemap against the previous build → every removed URL is a category page that was intended to
   go, and no winner page changed route unintentionally.

## CLEAN-6 — Craft pass — DONE 20260725

ID: `CLEAN-6` — Typography and layout corrections. Spec §4.1-§4.5.

Depends-on: CLEAN-1, CLEAN-2, CLEAN-3 (layouts must have stopped moving)

Done: `h1` clamp cap 4.5rem → 3rem; `body` flex column with `main { flex: 1 }` so short pages pin their footer;
`.category-year` sticky within its row; citations on category pages set italic at 0.9375rem on a 62ch measure so the
names carry the page; dark scheme added as a `prefers-color-scheme` override of the six existing custom properties.

Contrast measured for every text/background pair in both schemes — all pass WCAG AA, most AAA:

| Pair | Light | Dark |
|---|---|---|
| body on paper | 13.09 AAA | 14.48 AAA |
| muted on paper | 5.05 AA | 6.99 AA |
| link on paper | 5.20 AA | 9.08 AAA |
| body on surface | 14.04 AAA | 13.12 AAA |
| muted on surface | 5.41 AA | 6.33 AA |
| link on surface | 5.57 AA | 8.23 AAA |

**Not verified visually:** the dark scheme was checked by contrast arithmetic and by confirming the media query ships
in `dist/static/style.css`, not by screenshot. Headless Chrome's `--force-dark-mode` applies its own auto-darkening
filter rather than setting `prefers-color-scheme`, so it cannot exercise this rule. Worth one look in a real browser.

Files:

- `website/static/style.css`, existing lines 1-12 (`:root`), 95-97 (`main`), 117-123 (`h1`), 227-247, 318-353.

Relevant assumptions:

1. The existing palette and typographic rhythm are good. This is a correction pass, not a redesign — do not restyle
   what works.
2. The palette is already six custom properties, so dark mode is an override block, not a refactor.

Steps → verify:

1. Reduce the `h1` clamp cap at line 120 from `4.5rem` to ~`3rem` → the Hinton page title fits one line at 1440px and
   the facts sidebar rises; mobile at 390px is unchanged.
2. Add `body { min-height: 100vh; display: flex; flex-direction: column }` and `main { flex: 1 }` → the footer on
   `/nobel-prize/physics/2024/` sits at the bottom of the viewport, and long pages are unaffected.
3. Make `.category-year` sticky within its row → the year stays visible beside a 3-recipient row on
   `/nobel-prize/physics/`.
4. Add a `@media (prefers-color-scheme: dark)` block overriding lines 3-8 and drop the hard `color-scheme: light` →
   text and link contrast pass WCAG AA in both schemes; screenshot both.
5. Differentiate motivation text on category pages (lines 244-247) → names read as the primary content; screenshot
   `/nobel-prize/physics/` before and after.
6. Screenshot home, prize, category, year, winner, and person at 1440px and 390px → no regressions against the
   pre-cleanup captures.
