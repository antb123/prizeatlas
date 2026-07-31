# Static awards website implementation TODO

Implement `docs/specs/datasets-static-awards-website-20260725.md` on its own branch. Use conventional commits, do not merge
until reviewed, and squash-merge into `202607`.

## WEB-0 — Curated prize slugs

ID: `WEB-0` — Add unique SEO prize slugs to the ranking seed and live table.

Depends-on: none

Files:

- `award_ranking.toml`, existing lines 1-97;
- `scripts/load_award_ranking.py`, existing lines 1-141;
- `tests/test_load_award_ranking.py`, existing lines 1-136;
- `docs/specs/datasets-award-ranking-20260725.md`, existing lines 1-119.

Relevant assumptions:

2. Prize slugs are curated in `award_ranking.slug`; category, year, and winner slugs derive from source data.

Steps → verify:

1. Add the 14 exact SEO slugs from the website spec to `award_ranking.toml` → every block has one nonblank slug and
   the Economics slug remains distinct from the Nobel Prize.
2. Extend seed validation, the `Award` value, and table inserts with slug syntax and uniqueness → blank, malformed,
   or duplicate slug fixtures fail before writing.
3. In the existing transaction, add `slug TEXT NOT NULL DEFAULT ''` when absent, delete old rows, create unique index
   `award_ranking_slug_idx`, and insert the complete seed → an existing pre-slug table upgrades without indexing
   duplicate defaults.
4. Extend loader tests for new-table creation, existing-table migration, unique-index enforcement, score swaps,
   dry-run, and rollback → both schema and prior rows survive a forced failed migration or insert.
5. Update the ranking specification's goals, data model, files, and acceptance contract → it names the slug column,
   seed field, unique index, and migration behavior.
6. Back up the live database, run `uv run scripts/load_award_ranking.py`, and check `PRAGMA integrity_check` plus the
   `awards` table hash → 14 ranking rows contain the exact unique slugs and `awards` is unchanged.

## WEB-1 — Build pipeline

ID: `WEB-1` — Implement the read-only, threaded static website builder and sitemap.

Depends-on: WEB-0, WEB-2

Files:

- `website/build.py`, new lines 1-300;
- `website/build.py.lock`, generated lines 1-30.

Relevant assumptions:

1. The output is static HTML, CSS, and XML without an application server or client framework.
2. Prize slugs are curated in `award_ranking.slug`; category, year, and winner slugs are derived from source data.
3. Each award record produces one winner page nested below its routed year.
4. Category appears in a route only when that prize has multiple distinct nonblank categories.
5. SQLite is read once on the main thread and never accessed by workers.
6. Jinja is the only third-party dependency and uses inline `uv` script metadata.

Steps → verify:

1. Add Python 3.12 and Jinja PEP 723 metadata; run `uv lock --script website/build.py` → the adjacent lockfile is
   created and `uv run website/build.py --help` imports successfully.
2. Read and validate stored prize slugs and add the exact NFKD-to-ASCII category/year/winner slug function → fixtures
   produce `nobel-prize`, `turing-award`, `physics`, `1983-1984`, `ngo-bao-chau`, and
   `ernest-orlando-lawrence`; fixtures also prove that all remaining non-ASCII characters are discarded.
3. Require and validate a credential-free HTTPS `--base-url`, preserving an optional subpath → invalid schemes,
   credentials, queries, fragments, and missing hostnames fail before generation.
4. Open an explicit SQLite read transaction, validate the complete ranking and official URLs, count categories per
   prize, require four-digit year prefixes, split each prize at its 30 highest distinct four-digit year prefixes, and
   create immutable prize, category, year, and record-specific winner values → an instrumented fixture proves no
   worker accesses SQLite, same-prefix labels enter the same latest/older bucket, and invalid years fail.
5. Disambiguate colliding category base slugs by sorted source value and numeric suffix → both current Japan Prize
   category labels remain separate and routable in the focused fixture.
6. Build category-aware routes and breadcrumb/canonical data → Nobel Physics produces
   `/nobel-prize/physics/1939/ernest-orlando-lawrence/`, Turing omits a category segment, and a duplicate winner slug
   within one year route or duplicate year slug within one parent route fails.
7. Render distinct page jobs through `ThreadPoolExecutor(max_workers=8)` and consume the result iterator → a worker
   exception propagates and returns status 1.
8. Append each leading-slash-stripped route to the normalized base URL and generate either one bounded sitemap or
   numbered bounded sitemaps plus a root index → a small fixture uses one `urlset`; 50,001 short fixture routes use
   two numbered files and `sitemap.xml` as their index.
9. Compute every navigation, breadcrumb, and stylesheet link relative to each output page directory → fixtures from
   root through four nested route segments resolve inside `website/dist/` without root-relative paths.
10. Build into sibling directories whose names begin exactly `website/.dist-staging-` and
   `website/.dist-backup-`, then implement the conditional promotion, rollback, and cleanup sequence → forced render
   and promotion failures preserve any prior `website/dist/`; cleanup failure retains the backup, warns, and returns
   success with the new output active.
11. Emit only grep-able counts → logs identify the build outcome without names, motivations, or caller data.

## WEB-2 — HTML templates

ID: `WEB-2` — Create the semantic page templates and relative navigation.

Depends-on: none

Files:

- `website/templates/base.html`, new lines 1-70;
- `website/templates/index.html`, new lines 1-65;
- `website/templates/prize.html`, new lines 1-85;
- `website/templates/category.html`, new lines 1-70;
- `website/templates/year.html`, new lines 1-90;
- `website/templates/winner.html`, new lines 1-120.

Relevant assumptions:

1. The output is static HTML, CSS, and XML without an application server or client framework.
3. Each award record produces one winner page nested below its routed year.
4. Category appears in a route only when that prize has multiple distinct nonblank categories.
7. There is no JavaScript, image, hosting, or external-enrichment requirement.

Steps → verify:

1. Create a shared HTML shell with `<html lang="en">`, exact UTF-8 and viewport metadata, one title, exact
   description, canonical, `h1`, contracted breadcrumb labels, navigation, and depth-relative stylesheet link →
   every page-type fixture satisfies the complete document and SEO contract.
2. Render the homepage ranking with rank, prize name, score, blurb, and prize link → all 14 fixture prizes appear in
   descending score order.
3. Render each prize overview with score, blurb, reasoning, validated official link, and category links or direct
   year links, plus winners from the 30 highest distinct four-digit year prefixes and conditional native
   `More winners` details → multi-category, Turing, over-30-prefix, and under-30-prefix fixtures match the contract
   without JavaScript.
4. Render each category landing with its prize/category heading and descending years → every link stays within its
   prize hierarchy and ties on numeric prefix use descending source-year labels.
5. Render each year page with the exact contextual title/header and `award_record_id`-ordered entries → every name
   links to its nested winner page.
6. Render each winner record as a semantic article with the exact `PRIZE for Category Year — Name` title/header,
   contracted facts, source biography, affiliation, and record-specific award fields → no records are merged and no
   prose is invented; an Organization with only `laureate_type` renders a one-row facts panel.
7. Use Jinja variables without `safe` or equivalent bypasses → markup fixtures render as escaped text.

## WEB-3 — Presentation

ID: `WEB-3` — Add the small responsive stylesheet.

Depends-on: WEB-2

Files:

- `website/static/style.css`, new lines 1-200.

Relevant assumptions:

1. The output is static HTML, CSS, and XML without a client framework.
7. There is no JavaScript or image requirement.

Steps → verify:

1. Style the semantic elements with a restrained type scale, readable line length, clear ranking hierarchy, and
   visible focus states → homepage, prize, category, year, and winner fixtures remain readable at 360px and desktop
   widths.
2. Style the winner facts as an ordinary responsive aside that falls into document flow on narrow screens → facts
   remain readable without hiding or reordering article content.
3. Style breadcrumbs as restrained navigation with visible focus and current-page context → hierarchy remains clear
   without duplicating the main heading.
4. Use a mobile-first single column and one required `min-width: 64rem` transition to two-column prize groups and a
   side facts panel → manual browser checks recorded at 360px and 1,280px show no horizontal scrolling or reordered
   content.
5. Keep all presentation in one flat stylesheet with the original Danish furniture-store direction: warm
   off-white, charcoal, one muted natural accent, generous whitespace, thin rules, and precise alignment → no
   imports, framework, preprocessor, external font, gradient, shadow, animation, decorative image, or copied retail
   branding exists.

## WEB-4 — Focused tests

ID: `WEB-4` — Prove route hierarchy, contextual winner pages, SEO, sitemap correctness, and failed-build isolation.

Depends-on: WEB-1, WEB-2, WEB-3

Files:

- `tests/test_build_website.py`, new lines 1-300.

Relevant assumptions:

1. The output is static HTML, CSS, and XML.
2. Prize slugs are curated in `award_ranking.slug`; category, year, and winner slugs derive from source data.
3. Each award record produces one winner page nested below its routed year.
4. Category appears only for prizes with multiple nonblank categories.
5. SQLite is not shared with worker threads.

Steps → verify:

1. Build a fixture with stored SEO prize slugs, Nobel Physics, Turing, colliding Japan categories, accented and
   non-decomposing names, more than 30 distinct four-digit year prefixes, dual labels on one prefix, colliding year
   labels, an invalid year, an Organization, and repeated people across prizes → the full routing and failure
   contract is exercised.
2. Assert one homepage, one page per prize, required category pages, routed year pages, and one page per award record
   → the complete-navigation and contextual-winner scenarios are covered.
3. Verify `lang`, charset, viewport, exact title, `h1`, description, canonical, breadcrumb labels/links, source
   fields, empty sections, Organization facts, and non-merging for every page type, including a non-routed Economics
   category → the document, SEO, and Wikipedia-style scenarios are covered.
4. Inspect prize pages above and below the 30-prefix boundary → all labels sharing a prefix stay together, both
   visible and older groups use numeric-prefix/source-label/record ordering, every link is complete, categories are
   shown, and native `More winners` appears only when required.
5. Validate accepted and rejected base URLs and decode sitemap outputs → the current build uses one bounded `urlset`;
   50,001 short routes use two bounded numbered files plus a valid root index; locations retain the base subpath,
   use trailing slashes, and exclude assets and sitemap files.
6. Patch the executor and a worker to prove eight workers are requested and exceptions propagate → the threaded
   generation scenario is covered.
7. Supply HTML markup and unsafe official URLs → markup and sitemap locations are escaped and invalid URLs fail
   before generation.
8. Seed a previous output tree and force template, sitemap, and promotion failures → prior bytes remain unchanged;
   force backup cleanup failure → the new output remains active, the backup remains, and the command succeeds with a
   warning.
9. Parse all generated relative internal `href` values at every route depth → every link resolves to a generated
   file and no internal navigation or stylesheet link is root-relative.
10. Add colliding year labels and duplicate winner names inside their respective parent routes → each scoped
   collision fails before generation and preserves the previous output.
11. Run `uv run --with jinja2 python -m unittest tests/test_build_website.py` → all focused tests pass.

## WEB-5 — Repository integration

ID: `WEB-5` — Keep generated output out of Git and document the build.

Depends-on: WEB-1, WEB-2, WEB-3, WEB-4

Files:

- `.gitignore`, existing lines 1-3;
- `AGENTS.md`, existing lines 35-62.

Relevant assumptions:

1. The deliverable is generated static output.
6. Jinja is managed by the builder's inline script metadata.

Steps → verify:

1. Add exactly `/website/dist/`, `/website/.dist-staging-*/`, and `/website/.dist-backup-*/` to `.gitignore` → a
   completed and interrupted build using WEB-1's directory prefixes adds no generated paths to `git status --short`.
2. Document the stored prize slug source, database, required `--base-url`, command, generated directory, read-only
   website behavior, sitemap/index outputs, and non-versioned output → another contributor can run the build from
   `datasets/` without inferring paths.
3. Run `uv run website/build.py --base-url https://example.org/awards/` twice against the live database → both runs
   report 14 prizes, 98 categories, 1,654 year pages, 3,091 winner pages, 4,858 identical HTML files, and 4,858
   identical sitemap locations.
4. Run `sqlite3 awards.sqlite3 ".sha3sum --schema awards"` before and after the live builds → the `awards` hash is
   unchanged.
