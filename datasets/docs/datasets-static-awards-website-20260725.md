# Static awards website

## Goals

The dataset MUST build a complete static website from `awards.sqlite3` with no application server.

The site SHALL provide a ranked homepage, one overview page per prize family, and one page per prize/year
combination. Public paths use readable SEO slugs such as `/abel-prize/2003/`.

Generation MUST use a bounded thread pool for independent page rendering and writing.

## Background

`awards.sqlite3` is the source of truth under `AGENTS.md:35-58`. It currently contains 3,091 award rows, 14 prize
families in `award_ranking`, and 734 distinct prize/year combinations. `award_ranking` supplies each prize's QID,
display name, official URL, score, blurb, and reasoning.

Years are not uniformly four digits: 79 rows use values such as `1983/1984` and `2013 (special)`. These values must
remain unchanged for display but cannot be inserted directly into URL paths.

There is no existing website, template system, Python project metadata, or deployment configuration. `.gitignore:1-3`
currently ignores only the live SQLite files.

## Assumptions

1. **Load-bearing:** The deliverable is static HTML and CSS; no Flask, Django, API, search service, or client framework is required.
2. **Load-bearing:** Public prize and year slugs are derived from curated names; renaming a prize is therefore a breaking URL change.
3. **Load-bearing:** One page represents one prize/year combination and lists all matching award recipients.
4. **Load-bearing:** SQLite is read once on the main thread; worker threads never receive or open database connections.
5. Jinja is the only third-party dependency and is declared as inline `uv` script metadata.
6. The initial site has no JavaScript, images, canonical domain, sitemap, hosting workflow, or winner detail pages.

## Scope

Ten implementation files, approximately 760 lines:

| File | Current line range | Change |
| --- | --- | --- |
| `website/build.py` | new file, lines 1-185 | Read, validate, group, and render the site with eight worker threads. |
| `website/build.py.lock` | new generated file, lines 1-30 | Lock the inline Jinja dependency. |
| `website/templates/base.html` | new file, lines 1-45 | Shared document shell, metadata, navigation, and footer. |
| `website/templates/index.html` | new file, lines 1-55 | Ranked prize homepage. |
| `website/templates/prize.html` | new file, lines 1-70 | Prize description, reasoning, official link, and year links. |
| `website/templates/year.html` | new file, lines 1-80 | Prize/year heading and recipient list. |
| `website/static/style.css` | new file, lines 1-140 | Responsive semantic presentation without a CSS framework. |
| `tests/test_build_website.py` | new file, lines 1-140 | Slug, grouping, rendering, escaping, and failure tests. |
| `.gitignore` | existing lines 1-3 | Ignore `website/dist/` and temporary website build directories. |
| `AGENTS.md` | existing lines 35-62 | Document the build command, source, output, and generated-file rule. |

`website/dist/` is generated output and MUST NOT be versioned.

## URLs and page model

The build uses one slug function for prize names and year labels:

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
/static/style.css
```

QIDs remain the database join keys and MUST NOT appear in public paths. All internal links MUST be relative so the
site works at a domain root or under a hosting subpath.

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
nonblank. It MUST link back to the prize overview.

Templates MUST use semantic HTML. Jinja autoescaping and `StrictUndefined` MUST be enabled. Database text is
untrusted content and MUST never be marked safe.

## Build

The build command, run from `datasets/`, is:

```text
uv run website/build.py
```

`website/build.py` declares Python 3.12 and Jinja in PEP 723 inline metadata;
`uv lock --script website/build.py` produces the adjacent lockfile.

The control path is:

```text
SQLite read once -> validate and group -> page jobs -> 8 worker threads -> staging directory -> website/dist
```

The main thread MUST:

1. open one explicit read transaction and read all `award_ranking` rows and required `awards` columns from that
   SQLite snapshot;
2. verify that every live award QID has exactly one ranking row and official URL;
3. derive and validate unique prize and year slugs;
4. convert SQLite rows into ordinary immutable Python values;
5. create the complete list of page jobs.

`ThreadPoolExecutor(max_workers=8)` MUST render and write independent jobs to distinct paths in a staging directory.
The executor result iterator MUST be consumed so any worker exception fails the build. The existing `website/dist/`
MUST remain untouched until every page and static asset has been generated successfully.

Promotion MUST use this exact same-filesystem sequence:

1. if `website/dist/` exists, rename it to a unique sibling backup directory;
2. rename the completed staging directory to `website/dist/`;
3. if step 2 fails, rename the backup to `website/dist/` and propagate the error;
4. after successful promotion, remove the backup and report any cleanup failure.

The final log line identifies the operation and reports prize, prize/year, recipient, and generated-page counts.
Logs MUST NOT include motivations, filenames supplied as data, or other prose.

## Failure behavior

- A missing database, table, template, ranking row, required prize URL, empty slug, slug collision, render failure,
  or write failure MUST return exit status 1.
- A validation, render, or staging write failure MUST remove its staging directory and preserve the previous
  `website/dist/`; a promotion failure MUST attempt the specified rollback and fail loudly if rollback also fails.
- The builder MUST be read-only with respect to `awards.sqlite3`.
- No page may be silently skipped.

## Acceptance

### Requirement: Complete navigation — the build MUST generate every current prize and prize/year page

#### Scenario: current live database
- WHEN the builder runs against the current `awards.sqlite3`
- THEN it generates one homepage, 14 prize pages, and 734 prize/year pages
- AND every homepage prize link and prize year link resolves inside `website/dist/`

### Requirement: SEO paths — public paths MUST use safe deterministic slugs

#### Scenario: compound and special year labels
- WHEN the source year is `1983/1984` or `2013 (special)`
- THEN the path segment is `1983-1984` or `2013-special`
- AND the rendered heading preserves the original year label

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

## Verification

Implementation is complete when:

1. `uv run --with jinja2 python -m unittest tests/test_build_website.py` passes from `datasets/`.
2. `uv run website/build.py` succeeds and reports 749 generated HTML pages.
3. `tests/test_build_website.py` scans generated HTML and proves every relative internal `href` resolves.
4. a second build produces the same file paths and bytes.
5. the SHA3 of the `awards` table is unchanged before and after the build.

## Delivery constraints

- Create one branch for this specification.
- Use conventional commits and generate unit tests with the implementation.
- Do not merge until reviewed.
- Squash-merge into the `202607` month branch.

## Out of scope

Deployment, domains, canonical URLs, sitemap generation, JavaScript, search, analytics, maps, GeoJSON, winner pages,
and database changes are out of scope.
