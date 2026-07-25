# Static awards website

## Goals

The dataset MUST build a complete static website from `awards.sqlite3` with no application server.

The site SHALL provide a ranked homepage, one overview page per prize family, one page per prize/year combination,
and one Wikipedia-style article page per winner. Public paths use readable SEO slugs such as `/abel-prize/2003/`
and `/winners/albert-einstein-q937-individual/`.

Generation MUST use a bounded thread pool for independent page rendering and writing.

Every build MUST generate an XML sitemap containing the absolute URL of every public HTML page.

## Background

`awards.sqlite3` is the source of truth under `AGENTS.md:35-58`. It currently contains 3,091 award rows, 14 prize
families in `award_ranking`, 734 distinct prize/year combinations, 2,381 distinct nonblank laureate QID/type pairs,
and five rows without a laureate QID. Grouping by QID and laureate type with record-based fallbacks therefore
produces 2,386 winner pages.
`award_ranking` supplies each prize's QID, display name, official URL, score, blurb, and reasoning.

Years are not uniformly four digits: 79 rows use values such as `1983/1984` and `2013 (special)`. These values must
remain unchanged for display but cannot be inserted directly into URL paths.

Twelve current names map to more than one laureate QID, so a name-only winner slug would collide. Some QIDs also have
multiple source-name variants. `Q710597` identifies both an organization record and individual records, so QID alone
is not a safe winner key.

There is no existing website, template system, Python project metadata, canonical domain, or deployment
configuration. `.gitignore:1-3` currently ignores only the live SQLite files.

## Assumptions

1. **Load-bearing:** The deliverable is static HTML, CSS, and XML; no Flask, Django, API, search service, or client framework is required.
2. **Load-bearing:** Prize, year, and winner slugs are derived from source data; changing source names may therefore change public URLs.
3. **Load-bearing:** Rows sharing one nonblank `(laureate_wikidata_qid, laureate_type)` pair form one winner; each row without a QID forms its own winner.
4. **Load-bearing:** One page represents one prize/year combination and lists all matching award recipients.
5. **Load-bearing:** SQLite is read once on the main thread; worker threads never receive or open database connections.
6. Jinja is the only third-party dependency and is declared as inline `uv` script metadata.
7. The initial site has no JavaScript, images, hosting workflow, or external enrichment.

## Scope

Eleven implementation files, approximately 1,050 lines:

| File | Current line range | Change |
| --- | --- | --- |
| `website/build.py` | new file, lines 1-240 | Read, validate, group, render the site with eight worker threads, and generate the sitemap. |
| `website/build.py.lock` | new generated file, lines 1-30 | Lock the inline Jinja dependency. |
| `website/templates/base.html` | new file, lines 1-50 | Shared document shell, metadata, navigation, and footer. |
| `website/templates/index.html` | new file, lines 1-55 | Ranked prize homepage. |
| `website/templates/prize.html` | new file, lines 1-75 | Prize description, reasoning, official link, and year links. |
| `website/templates/year.html` | new file, lines 1-85 | Prize/year heading and linked recipient list. |
| `website/templates/winner.html` | new file, lines 1-120 | Wikipedia-style winner article, facts, awards, and affiliations. |
| `website/static/style.css` | new file, lines 1-180 | Responsive semantic presentation, including the winner fact panel. |
| `tests/test_build_website.py` | new file, lines 1-210 | Slug, grouping, sitemap, rendering, escaping, and failure tests. |
| `.gitignore` | existing lines 1-3 | Ignore `website/dist/` and temporary website build directories. |
| `AGENTS.md` | existing lines 35-62 | Document the build command, source, output, and generated-file rule. |

`website/dist/` is generated output and MUST NOT be versioned.

## URLs and page model

The build uses one slug function for prize names, year labels, winner names, laureate types, and fallback record IDs:

1. convert to lowercase;
2. replace each run of characters outside `a-z` and `0-9` with one hyphen;
3. trim leading and trailing hyphens;
4. reject an empty result or a collision within its scope.

Examples:

| Source | Slug |
| --- | --- |
| Abel Prize | `abel-prize` |
| Sveriges Riksbank Prize in Economic Sciences | `sveriges-riksbank-prize-in-economic-sciences` |
| 2003 | `2003` |
| 1983/1984 | `1983-1984` |
| 2013 (special) | `2013-special` |

The generated paths are:

```text
/index.html
/{prize-slug}/index.html
/{prize-slug}/{year-slug}/index.html
/winners/{winner-slug}/index.html
/sitemap.xml
/static/style.css
```

Prize QIDs remain database join keys and MUST NOT appear in prize paths. Winner identity and slugging use:

1. require every nonblank QID to match `Q[1-9][0-9]*` and have a nonblank `laureate_type`;
2. group every row with the same nonblank `(laureate_wikidata_qid, laureate_type)` pair;
3. treat each row without a laureate QID as a separate winner keyed by `award_record_id`;
4. choose the first nonblank `full_name` after sorting the group's rows by `award_record_id`;
5. for a QID group, join the slugged name, lowercase QID, and slugged laureate type with hyphens;
6. for a fallback group, join the slugged name and slugged `award_record_id` with a hyphen;
7. reject an empty component or final slug collision.

The identity suffix keeps winner URLs unique while retaining the name for search engines. All internal links MUST be
relative so the site works at a domain root or under a hosting subpath.

## Content

### Homepage

The homepage MUST list all prize families by descending score. Each entry contains rank, name, score, blurb, and a
link to the prize page.

### Prize page

Each prize page MUST contain name, score, blurb, reasoning, official URL, and links to its years in descending order.
Before an official URL is inserted into `href`, the builder MUST require an HTTPS scheme, a nonblank hostname, and no
embedded username or password.

### Prize/year page

Each prize/year page MUST display the original year label and every matching recipient ordered by
`award_record_id`. Each recipient entry contains `full_name`, `category` when nonblank, and `motivation` when
nonblank. The recipient name MUST link to its winner page, and the page MUST link back to the prize overview.

### Winner page

Each winner page MUST use a simple Wikipedia-style article layout without copying Wikipedia content:

- the selected `full_name` as the article heading;
- a compact facts panel containing `laureate_type`, `birth_date`, `birth_year`, `birth_city`, `birth_country`,
  `citizenship_countries`, `death_date`, `death_city`, and `death_country`;
- the first nonblank `biographical_note` as the lead when present;
- a deduplicated list of nonblank `(affiliation_name, affiliation_city, affiliation_country)` tuples collected from
  every grouped row;
- an awards section containing every grouped award row in `award_record_id` order, with `prize_name`, year, category,
  motivation, and a link to the corresponding prize/year page when those fields are nonblank.

For each scalar fact and the lead, the page MUST use the first nonblank value after sorting rows by
`award_record_id`. Affiliation tuples MUST retain first-occurrence order and omit only tuples whose three values are
all blank. The page MUST preserve source values verbatim, omit empty facts and sections, and MUST NOT generate
biography prose, fetch an image, or call Wikipedia or Wikidata.

Templates MUST use semantic HTML. Jinja autoescaping and `StrictUndefined` MUST be enabled. Database text is
untrusted content and MUST never be marked safe.

## Sitemap

The builder MUST require `--base-url` because sitemap locations are absolute. The base URL MUST use HTTPS, contain a
hostname, contain no credentials, query, or fragment, and MAY contain a deployment subpath. It is normalized to one
trailing slash without discarding that subpath.

`sitemap.xml` MUST use the sitemap protocol namespace and contain one `<url><loc>` entry for every generated HTML
route: homepage, prize pages, prize/year pages, and winner pages. Locations MUST be XML-escaped, sorted by route, and
use public trailing-slash URLs rather than `index.html`. Static assets and `sitemap.xml` itself MUST NOT be listed.
Each location MUST be constructed by appending the public route with its leading slash removed to the normalized
base URL; origin-relative resolution that discards a base subpath is forbidden. The current site fits in one sitemap,
so sitemap indexes and splitting are out of scope.

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
3. verify that every live award QID has exactly one ranking row and official URL;
4. group winner identities and resolve their deterministic source values;
5. derive and validate unique prize, year, and winner slugs;
6. convert SQLite rows into ordinary immutable Python values;
7. create the complete list of page jobs and public routes.

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

The final log line identifies the operation and reports prize, prize/year, winner, recipient, sitemap-URL, and
generated-page counts. Logs MUST NOT include names, motivations, filenames supplied as data, or other prose.

## Failure behavior

- A missing or invalid base URL, database, table, template, ranking row, required prize URL, winner identity, empty
  slug, slug collision, render failure, sitemap failure, or write failure MUST return exit status 1.
- A validation, render, or staging write failure MUST remove its staging directory and preserve the previous
  `website/dist/`; a promotion failure MUST attempt the conditional rollback and fail loudly if rollback also fails.
- A backup-cleanup warning MUST identify only the operation and backup path, without changing the successful build
  result.
- The builder MUST be read-only with respect to `awards.sqlite3`.
- No page may be silently skipped.

## Acceptance

### Requirement: Complete navigation — the build MUST generate every current prize and prize/year page

#### Scenario: current live database
- WHEN the builder runs against the current `awards.sqlite3` with a valid base URL
- THEN it generates one homepage, 14 prize pages, 734 prize/year pages, and 2,386 winner pages
- AND every homepage, prize, year, award, and winner link resolves inside `website/dist/`

### Requirement: SEO paths — public paths MUST use safe deterministic slugs

#### Scenario: compound and special year labels
- WHEN the source year is `1983/1984` or `2013 (special)`
- THEN the path segment is `1983-1984` or `2013-special`
- AND the rendered heading preserves the original year label

### Requirement: Winner identity — repeated awards MUST resolve to one Wikipedia-style winner page

#### Scenario: one QID/type pair has multiple award rows
- WHEN several award rows share one nonblank laureate QID and laureate type
- THEN they link to one name, QID, and type winner route
- AND the winner page lists every award and its prize/year link
- AND the page displays only existing biography, fact, and affiliation values

#### Scenario: one QID represents an individual and an organization
- WHEN two award groups share a QID but have different laureate types
- THEN the type suffixes produce separate winner pages

#### Scenario: the same name belongs to different QIDs
- WHEN two winner groups have the same selected `full_name`
- THEN their QID suffixes produce distinct public routes

#### Scenario: a laureate QID is missing
- WHEN an award row has no laureate QID
- THEN it receives its own winner page whose slug ends with the award record ID

### Requirement: Sitemap — every public HTML page MUST have one absolute sitemap location

#### Scenario: site deployed below a domain subpath
- WHEN the base URL is `https://example.org/awards/`
- THEN every `<loc>` begins with that exact normalized base
- AND the sitemap contains 3,135 sorted, unique page locations
- AND it contains neither `index.html`, `sitemap.xml`, nor the stylesheet

#### Scenario: invalid sitemap origin
- WHEN the base URL uses HTTP, credentials, a query, a fragment, or no hostname
- THEN the build returns status 1 before page generation
- AND the previous output remains unchanged

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
2. `uv run website/build.py --base-url https://example.org/awards/` succeeds and reports 3,135 generated HTML pages
   and 3,135 sitemap URLs.
3. `tests/test_build_website.py` scans generated HTML and proves every relative internal `href` resolves.
4. the tests decode `sitemap.xml` and prove its unique absolute locations equal the generated public HTML routes.
5. winner fixtures prove QID/type grouping, same-QID type separation, name collisions, record-ID fallback,
   deterministic fact selection, affiliation-tuple deduplication, escaping, empty-section omission, and complete
   award links.
6. a second build produces the same file paths and bytes.
7. the SHA3 of the `awards` table is unchanged before and after the build.

## Delivery constraints

- Create one branch for this specification.
- Use conventional commits and generate unit tests with the implementation.
- Do not merge until reviewed.
- Squash-merge into the `202607` month branch.

## Out of scope

Deployment, domain selection, sitemap indexes, JavaScript, search, analytics, maps, GeoJSON, images, external
biography enrichment, Wikipedia or Wikidata calls, and database changes are out of scope.
