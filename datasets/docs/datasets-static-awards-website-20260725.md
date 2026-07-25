# Static awards website

## Goals

The dataset MUST build a complete static website from `awards.sqlite3` with no application server.

The site SHALL provide a ranked homepage, one overview page per prize family, category landing pages where a prize
has multiple categories, one year page per routed prize/category/year combination, and one Wikipedia-style article
page per award record. Public paths use curated SEO routes such as `/nobel-prize/physics/1939/`,
`/turing-award/1989/`, and `/nobel-prize/physics/1921/albert-einstein/`.

Generation MUST use a bounded thread pool for independent page rendering and writing.

Every build MUST generate an XML sitemap containing the absolute URL of every public HTML page.

Every page MUST have a unique factual title, one descriptive `h1`, a meta description, breadcrumbs where the page is
below the homepage, and an absolute canonical URL.

DESIGN style is clean DANISH furniture store

## Background

`awards.sqlite3` is the source of truth under `AGENTS.md:35-58`. It currently contains 3,091 award rows, 14 prize
families in `award_ranking`, 98 categories among multi-category prizes, and 1,654 routed year combinations. One
winner page per award record produces 3,091 contextual winner pages and 4,858 HTML pages overall.
`award_ranking` supplies each prize's QID, display name, official URL, score, blurb, and reasoning. It currently has
no prize slug; this feature adds one required curated SEO slug per ranking row.

Years are not uniformly four digits: 79 rows use values such as `1983/1984` and `2013 (special)`. These values must
remain unchanged for display but cannot be inserted directly into URL paths. Every current year label begins with a
four-digit year, which supplies the numeric ordering used by prize-page recency.

No current prize/category/year route contains duplicate `full_name` values, so the winner name is sufficient within
its award context. The builder must still reject a future collision rather than overwrite a page.

There is no existing website, template system, Python project metadata, canonical domain, or deployment
configuration. `.gitignore:1-3` currently ignores only the live SQLite files.

## Assumptions

1. **Load-bearing:** The deliverable is static HTML, CSS, and XML; no Flask, Django, API, search service, or client framework is required.
2. **Load-bearing:** Prize slugs are curated in `award_ranking.slug`; category, year, and winner slugs are derived from source data.
3. **Load-bearing:** Each `award_record_id` produces one winner page nested below its prize/category/year route.
4. **Load-bearing:** Category appears in the route only when that prize has more than one distinct nonblank category.
5. **Load-bearing:** SQLite is read once on the main thread; worker threads never receive or open database connections.
6. Jinja is the only third-party dependency and is declared as inline `uv` script metadata.
7. The initial site has no JavaScript, images, hosting workflow, or external enrichment.

## Scope

Sixteen implementation files, approximately 1,500 lines, plus the live `award_ranking` table update:

| File | Current line range | Change |
| --- | --- | --- |
| `award_ranking.toml` | existing lines 1-97 | Add one curated SEO slug to each prize. |
| `scripts/load_award_ranking.py` | existing lines 1-141 | Validate, migrate, and load the slug column and unique index. |
| `tests/test_load_award_ranking.py` | existing lines 1-136 | Prove slug validation, uniqueness, migration, and rollback. |
| `docs/datasets-award-ranking-20260725.md` | existing lines 1-119 | Add the slug to the ranking-table contract. |
| `website/build.py` | new file, lines 1-300 | Read, validate, route, render the site with eight worker threads, and generate the sitemap. |
| `website/build.py.lock` | new generated file, lines 1-30 | Lock the inline Jinja dependency. |
| `website/templates/base.html` | new file, lines 1-60 | Shared document shell, SEO metadata, breadcrumbs, navigation, and footer. |
| `website/templates/index.html` | new file, lines 1-65 | Ranked prize homepage. |
| `website/templates/prize.html` | new file, lines 1-85 | Prize description, reasoning, official link, and category or year links. |
| `website/templates/category.html` | new file, lines 1-70 | Category landing page and year links. |
| `website/templates/year.html` | new file, lines 1-90 | Prize/category/year heading and linked recipient list. |
| `website/templates/winner.html` | new file, lines 1-120 | Wikipedia-style winner article, facts, award, and affiliation. |
| `website/static/style.css` | new file, lines 1-200 | Responsive semantic presentation, breadcrumbs, and winner fact panel. |
| `tests/test_build_website.py` | new file, lines 1-270 | Route, recency, SEO, sitemap, rendering, escaping, and failure tests. |
| `.gitignore` | existing lines 1-3 | Ignore `website/dist/` and temporary website build directories. |
| `AGENTS.md` | existing lines 35-62 | Document the build command, source, output, and generated-file rule. |

`website/dist/` is generated output and MUST NOT be versioned.

## URLs and page model

`award_ranking.toml` and `award_ranking` MUST contain these curated prize slugs:

| Prize | Prize slug |
| --- | --- |
| Nobel Prize | `nobel-prize` |
| Fields Medal | `fields-medal` |
| Turing Award | `turing-award` |
| Max Planck Medal | `max-planck-medal` |
| Abel Prize | `abel-prize` |
| Lasker Award | `lasker-award` |
| Canada Gairdner International Award | `canada-gairdner-international-award` |
| Wolf Prize | `wolf-prize` |
| Kyoto Prize | `kyoto-prize` |
| Crafoord Prize | `crafoord-prize` |
| Shaw Prize | `shaw-prize` |
| Japan Prize | `japan-prize` |
| Breakthrough Prize | `breakthrough-prize` |
| Sveriges Riksbank Prize in Economic Sciences | `sveriges-riksbank-prize-in-economic-sciences` |

The ranking loader MUST require every seed slug to match `[a-z0-9]+(?:-[a-z0-9]+)*` and reject duplicate slugs before
writing. In its existing transaction it MUST add `slug TEXT NOT NULL DEFAULT ''` when the column is absent, delete
the old ranking rows, create the unique `award_ranking_slug_idx` index, and insert the complete seed including slug.
This order avoids indexing identical migration defaults; any failure MUST roll back the schema and data changes. The
builder MUST read the stored slug directly and fail on a missing, invalid, or duplicate live value.

Category, year, and winner segments use one standard-library slug function:

1. normalize with Unicode NFKD;
2. encode to ASCII while dropping combining marks, then decode and lowercase;
3. replace each run of characters outside `a-z` and `0-9` with one hyphen;
4. trim leading and trailing hyphens;
5. reject an empty result.

Examples include `Physics` to `physics`, `1983/1984` to `1983-1984`, `2013 (special)` to `2013-special`, and
`Ngô Bao Châu` to `ngo-bao-chau`.

Within each prize, category values are grouped by their base slug. If more than one distinct value shares a base,
sort the original values by Unicode code point and assign the base slug to the first, then `-2`, `-3`, and so on.
This preserves all 98 current categories, including the two Japan Prize labels that both reduce to
`electronics-information-and-communication`. A duplicate winner slug within one year route remains an error.

For a prize with more than one distinct nonblank category, the site MUST generate a category landing page and put
the category between prize and year. For a prize with zero or one distinct nonblank category, the category segment
MUST be omitted:

```text
/index.html
/{prize-slug}/index.html
/{prize-slug}/{category-slug}/index.html
/{prize-slug}/{category-slug}/{year-slug}/index.html
/{prize-slug}/{category-slug}/{year-slug}/{winner-slug}/index.html
/{prize-slug}/{year-slug}/index.html
/{prize-slug}/{year-slug}/{winner-slug}/index.html
/sitemap.xml
/static/style.css
```

Thus Nobel Physics uses `/nobel-prize/physics/1939/`, while the Turing Award uses `/turing-award/1989/`. Each award
record gets one winner page below its year route, such as
`/nobel-prize/physics/1939/ernest-orlando-lawrence/`. Winner slugs need only be unique within that year route; a
collision MUST fail before any output is published. There is no `/winners/` namespace.

All internal links MUST be relative so the site works at a domain root or under a hosting subpath.

## Content

### Homepage

The homepage MUST list all prize families by descending score. Each entry contains rank, name, score, blurb, and a
link to the prize page.

### Prize page

Each prize page MUST contain name, score, blurb, reasoning, and official URL. A multi-category prize page links to
its categories; a zero- or one-category prize page links directly to its years.

Below that introduction, the page MUST list all winner records from the 30 highest distinct four-digit year prefixes
for that prize. Records are grouped by displayed source year, ordered by numeric year descending, source-year label
descending by Unicode code point, then `award_record_id`, and link to their contextual winner pages. Multi-category
prizes MUST show each record's category. When older records exist, they MUST appear in a native `<details>` element
whose `<summary>` is `More winners`; when no older records exist, the disclosure MUST be omitted. This is static HTML
and MUST NOT require JavaScript.

Before an official URL is inserted into `href`, the builder MUST require an HTTPS scheme, a nonblank hostname, and no
embedded username or password.

### Category page

Each category page MUST display the prize name and original category value and link to its years by four-digit prefix
descending, then source-year label descending by Unicode code point.

### Year page

Each year page MUST display the prize, routed category when present, original year label, and every matching award
record ordered by `award_record_id`. Each entry contains `full_name` and `motivation` when nonblank. The name MUST
link to that record's winner page.

### Winner page

Each award record's winner page MUST use a simple Wikipedia-style article layout without copying Wikipedia content:

- a heading in the exact contextual form defined by the SEO contract below;
- a compact facts panel containing `laureate_type`, `birth_date`, `birth_year`, `birth_city`, `birth_country`,
  `citizenship_countries`, `death_date`, `death_city`, and `death_country`;
- `biographical_note` as the lead when nonblank;
- the nonblank `affiliation_name`, `affiliation_city`, and `affiliation_country` values;
- an award section containing `prize_name`, category, year, motivation, prize share, and a link to the parent year.

The page MUST preserve source values verbatim, omit empty facts and sections, and MUST NOT generate biography prose,
fetch an image, combine other award records, or call Wikipedia or Wikidata.

Templates MUST use semantic HTML. Jinja autoescaping and `StrictUndefined` MUST be enabled. Database text is
untrusted content and MUST never be marked safe.

## Responsive presentation

The site MUST use mobile-first semantic HTML and CSS. At 360 CSS pixels, every page MUST use one readable content
column without horizontal scrolling; navigation, breadcrumbs, `More winners`, and links MUST wrap and remain easy to
tap. Winner facts MUST remain in normal document flow.

At the single `min-width: 64rem` desktop breakpoint, prize winner-year groups MUST change to two columns and the
winner article MUST change to a main-content-plus-facts-panel layout. At 1,280 CSS pixels this layout MUST have a
readable maximum width. The document order and all content MUST remain the same at both widths. No information may
require hover, and keyboard focus MUST be visible.

Presentation MUST live in the single `website/static/style.css` file and use a clean flat aesthetic: strong
typography, generous whitespace, a restrained color palette, and simple borders for hierarchy. It MUST NOT use a CSS
framework, preprocessor, external font, gradient, drop shadow, animation, or decorative image.

The visual direction is an original, understated Danish furniture-store aesthetic: warm off-white surfaces,
charcoal text, one muted natural accent, generous margins, thin rules, precise alignment, and quiet editorial
hierarchy. It MUST remain high-contrast and functional rather than imitating any specific retailer or adding
ornamental Scandinavian motifs.

## SEO titles and headings

Every HTML page MUST contain exactly one nonblank `<title>`, one `<meta name="description">`, one absolute
`<link rel="canonical">`, and one `h1`. The canonical URL MUST equal that page's sitemap URL. Titles, descriptions,
headings, and breadcrumbs MUST be rendered from escaped source values using these templates:

| Page | `<title>` and `h1` |
| --- | --- |
| Homepage | `Prestigious Awards and Winners` |
| Prize | `{Prize Name}: Winners by Year` |
| Category | `{Prize Name} for {Category}: Winners by Year` |
| Year with category | `{Prize Name} for {Category} {Year}: Winners` |
| Year without category | `{Prize Name} {Year}: Winners` |
| Winner with category | `{Prize Name} for {Category} {Year} — {Full Name}` |
| Winner without category | `{Prize Name} {Year} — {Full Name}` |

Thus the contextual winner heading is `Nobel Prize for Physics 1939 — Ernest Orlando Lawrence`; a Turing winner uses
`Turing Award 1989 — {Full Name}`. Descriptions MUST use the same factual prize, category, year, and winner values in
one short sentence. Pages below the homepage MUST render relative breadcrumbs for every ancestor route. The site
MUST NOT emit `meta keywords`, repeated hidden headings, or generated keyword lists.

In these templates, “with category” means any nonblank source `category`, even when that single category is omitted
from the URL. For example, an Economics title still contains `for Economics`; only a blank source category uses the
without-category form.

## Sitemap

The builder MUST require `--base-url` because sitemap locations are absolute. The base URL MUST use HTTPS, contain a
hostname, contain no credentials, query, or fragment, and MAY contain a deployment subpath. It is normalized to one
trailing slash without discarding that subpath.

The sitemap output MUST cover every generated HTML route: homepage, prize pages, category pages, year pages, and
winner pages. Page locations MUST use the sitemap protocol namespace, be XML-escaped, be sorted by route, and use
public trailing-slash URLs rather than `index.html`. Static assets and sitemap files themselves MUST NOT be page
locations.
Each location MUST be constructed by appending the public route with its leading slash removed to the normalized
base URL; origin-relative resolution that discards a base subpath is forbidden.

When the sorted locations fit within both 50,000 URLs and 52,428,800 UTF-8 bytes, `sitemap.xml` MUST be the single
`urlset`; this is the current 4,858-page output. Otherwise the builder MUST split complete URL entries, without
changing order, into `sitemap-0001.xml`, `sitemap-0002.xml`, and so on, with each file respecting both limits.
`sitemap.xml` then MUST be a `sitemapindex` containing the absolute URL of every numbered file. The builder MUST fail
before promotion if the index itself would exceed 50,000 sitemap entries or 52,428,800 bytes.

## Build

The build command, run from `datasets/`, is:

```text
uv run website/build.py --base-url https://example.org/awards/
```

`website/build.py` declares Python 3.12 and Jinja in PEP 723 inline metadata;
`uv lock --script website/build.py` produces the adjacent lockfile.

The control path is:

```text
validate base URL -> SQLite read once -> validate and group -> page jobs -> 8 worker threads -> sitemap -> staging directory -> website/dist
```

The main thread MUST:

1. validate and normalize the required base URL;
2. open one explicit read transaction and read all `award_ranking` rows and required `awards` columns from that
   SQLite snapshot;
3. verify that every live award QID has exactly one ranking row, official URL, and valid stored prize slug;
4. validate each year label's four-digit prefix, count distinct nonblank categories per prize, and construct the
   required category-aware hierarchy and 30-year prize-page split;
5. derive and validate category, year, and winner slugs within their route scopes;
6. convert SQLite rows into ordinary immutable Python values;
7. create the complete list of page jobs, breadcrumb ancestors, canonical URLs, and public routes.

`ThreadPoolExecutor(max_workers=8)` MUST render and write independent jobs to distinct paths in a staging directory.
The executor result iterator MUST be consumed so any worker exception fails the build. After every HTML page succeeds,
the main thread MUST generate `sitemap.xml` from the already validated route list. The existing `website/dist/` MUST
remain untouched until every page, static asset, and sitemap has been generated successfully.

Promotion MUST use this exact same-filesystem sequence:

1. if `website/dist/` exists, rename it to a unique sibling backup directory;
2. rename the completed staging directory to `website/dist/`;
3. if step 2 fails and a backup was created, rename that backup to `website/dist/`, then propagate the original
   error; if no backup was created, propagate the error directly;
4. after successful promotion, remove any backup; if cleanup fails, retain the backup, log a warning, and keep the
   successful exit status because the new `website/dist/` is already active.

The final log line identifies the operation and reports prize, category, year-page, winner-page, recipient,
sitemap-URL, and generated-page counts. Logs MUST NOT include names, motivations, filenames supplied as data, or
other prose.

## Failure behavior

- A missing or invalid base URL, database, table, template, ranking row, required prize URL, stored prize slug, year
  prefix, empty slug, scoped slug collision, render failure, sitemap failure, or write failure MUST return exit
  status 1.
- A validation, render, or staging write failure MUST remove its staging directory and preserve the previous
  `website/dist/`; a promotion failure MUST attempt the conditional rollback and fail loudly if rollback also fails.
- A backup-cleanup warning MUST identify only the operation and backup path, without changing the successful build
  result.
- The builder MUST be read-only with respect to `awards.sqlite3`.
- No page may be silently skipped.

## Acceptance

### Requirement: Stored prize slugs — `award_ranking` MUST own every curated prize route

#### Scenario: existing ranking table
- WHEN the loader runs against the current table without a slug column
- THEN it adds the column and unique index and loads all 14 exact SEO slugs
- AND `PRAGMA integrity_check` returns `ok`
- AND the `awards` table remains unchanged

#### Scenario: invalid or duplicate seed slug
- WHEN the seed contains a malformed or duplicate slug
- THEN the loader returns status 1
- AND the previous ranking schema and rows remain unchanged

### Requirement: Complete navigation — the build MUST generate every current prize, category, year, and winner page

#### Scenario: current live database
- WHEN the builder runs against the current `awards.sqlite3` with a valid base URL
- THEN it generates one homepage, 14 prize pages, 98 category pages, 1,654 year pages, and 3,091 winner pages
- AND all 4,858 HTML pages are reachable through valid relative navigation

### Requirement: Prize landing — each prize page MUST show its latest 30 years of winners first

#### Scenario: prize with more than 30 years
- WHEN a prize has award records across more than 30 distinct four-digit year prefixes
- THEN winners from the 30 highest prefixes are visible in descending year groups
- AND every older winner remains available inside `More winners`

#### Scenario: prize with 30 or fewer years
- WHEN a prize has award records across at most 30 distinct four-digit year prefixes
- THEN every winner is visible without a `More winners` disclosure

#### Scenario: invalid year prefix
- WHEN a source year does not begin with four digits
- THEN the build returns status 1 before page generation
- AND the previous output remains unchanged

### Requirement: SEO paths — public paths MUST use safe deterministic slugs

#### Scenario: multi-category prize
- WHEN the 1939 Nobel Physics page is generated
- THEN its public route is `/nobel-prize/physics/1939/`
- AND its winner pages are nested below that route

#### Scenario: zero- or one-category prize
- WHEN the 1989 Turing Award page is generated
- THEN its public route is `/turing-award/1989/`
- AND no redundant category segment appears

#### Scenario: compound and special year labels
- WHEN the source year is `1983/1984` or `2013 (special)`
- THEN the path segment is `1983-1984` or `2013-special`
- AND the rendered heading preserves the original year label

#### Scenario: missing prize slug
- WHEN a live ranking row has no valid stored prize slug
- THEN the build returns status 1 before page generation
- AND the previous output remains unchanged

### Requirement: Contextual winner page — every award record MUST have one nested Wikipedia-style page

#### Scenario: Nobel Physics winner
- WHEN the 1939 Ernest Orlando Lawrence record is generated
- THEN its public route is `/nobel-prize/physics/1939/ernest-orlando-lawrence/`
- AND its title and `h1` are `Nobel Prize for Physics 1939 — Ernest Orlando Lawrence`
- AND no generated route begins with `/winners/`

#### Scenario: repeated person across prizes
- WHEN one person has multiple award records
- THEN each record has one page below its own award route
- AND no record is merged into another award page

#### Scenario: duplicate winner slug in one year route
- WHEN two records in the same routed year derive the same winner slug
- THEN the build returns status 1 before page generation
- AND the previous output remains unchanged

### Requirement: SEO metadata — every HTML page MUST have unique contextual search metadata

#### Scenario: rendered winner page
- WHEN a winner page is rendered
- THEN it has exactly one contextual title, meta description, canonical URL, and `h1`
- AND its breadcrumbs link to the homepage, prize, optional category, and year ancestors
- AND its canonical URL equals its sitemap location

### Requirement: Responsive flat presentation — every page MUST work on mobile and desktop

#### Scenario: narrow mobile viewport
- WHEN a page is rendered at 360 CSS pixels wide
- THEN content, breadcrumbs, winner lists, facts, and `More winners` fit without horizontal scrolling
- AND interactive elements remain visible and keyboard-focusable

#### Scenario: desktop viewport
- WHEN a page is rendered at 1,280 CSS pixels wide
- THEN the 64rem breakpoint produces the required two-column prize and winner layouts at a readable maximum width
- AND the stylesheet contains no framework, external font, gradient, shadow, animation, or decorative image

### Requirement: Sitemap — every public HTML page MUST have one absolute sitemap location

#### Scenario: site deployed below a domain subpath
- WHEN the base URL is `https://example.org/awards/`
- THEN every `<loc>` begins with that exact normalized base
- AND the sitemap contains 4,858 sorted, unique page locations
- AND it contains neither `index.html`, `sitemap.xml`, nor the stylesheet

#### Scenario: invalid sitemap origin
- WHEN the base URL uses HTTP, credentials, a query, a fragment, or no hostname
- THEN the build returns status 1 before page generation
- AND the previous output remains unchanged

#### Scenario: more than 50,000 sitemap locations
- WHEN 50,001 short fixture routes are serialized
- THEN `sitemap.xml` is a sitemap index
- AND `sitemap-0001.xml` contains 50,000 locations and `sitemap-0002.xml` contains one
- AND every XML file remains within the protocol byte limit

### Requirement: Threaded generation — page jobs MUST execute through the bounded executor

#### Scenario: successful threaded build
- WHEN more than one page job exists
- THEN the builder submits all jobs to `ThreadPoolExecutor(max_workers=8)`
- AND any worker exception makes the command fail

### Requirement: Safe rendering — database prose MUST be escaped

#### Scenario: markup in a fixture value
- WHEN a fixture name or motivation contains HTML markup
- THEN the rendered page contains escaped text
- AND no source value is interpreted as HTML

#### Scenario: unsafe official URL
- WHEN a fixture ranking URL is not valid credential-free HTTPS
- THEN the build returns status 1 before page generation
- AND the previous output remains unchanged

### Requirement: Failed build isolation — a failed build MUST preserve the previous output

#### Scenario: template failure
- WHEN one page render raises an exception
- THEN the command returns status 1
- AND the prior `website/dist/` remains unchanged

#### Scenario: old-backup cleanup failure
- WHEN every new output is promoted but removing the old backup fails
- THEN the command logs a warning and returns status 0
- AND the new `website/dist/` remains active and the backup remains available

## Verification

Implementation is complete when:

1. `uv run --with jinja2 python -m unittest tests/test_build_website.py` passes from `datasets/`.
2. `uv run website/build.py --base-url https://example.org/awards/` succeeds and reports 4,858 generated HTML pages
   and 4,858 sitemap URLs.
3. `tests/test_build_website.py` scans generated HTML and proves every relative internal `href` resolves.
4. the tests decode a single sitemap and a synthetic indexed sitemap and prove their unique absolute page locations
   equal the supplied public HTML routes.
5. ranking and route fixtures prove all 14 stored SEO prize slugs, conditional category segments, scoped category
   disambiguation, scoped winner collisions, special-year slugs, Unicode transliteration, and absence of `/winners/`.
6. rendered-page fixtures prove the exact SEO title and `h1` templates, descriptions, canonicals, breadcrumbs,
   escaping, blank-section omission, and record-specific award content.
7. prize fixtures prove the 30-year split, numeric and source-label descending order, conditional `More winners`,
   category labels, complete record links, and invalid-year failure.
8. manual browser checks recorded in the implementation handoff at 360 and 1,280 CSS pixels prove the responsive and
   flat-style scenarios without horizontal scrolling.
9. a second build produces the same file paths and bytes.
10. `uv run python -m unittest tests/test_load_award_ranking.py` passes, the live table has the unique slug index and
    14 exact slug values, and the SHA3 of `awards` is unchanged by the ranking load and website build.

## Delivery constraints

- Create one branch for this specification.
- Use conventional commits and generate unit tests with the implementation.
- Do not merge until reviewed.
- Squash-merge into the `202607` month branch.

## Out of scope

Deployment, domain selection, JavaScript, search, analytics, maps, GeoJSON, images, external
biography enrichment, and Wikipedia or Wikidata calls are out of scope.
