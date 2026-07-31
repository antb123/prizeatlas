# Explorer integration into the awards website

## Goals

Serve the standalone data explorer as a first-class page of the awards website at `/explorer/`, so it carries the site
header, navigation, breadcrumbs, footer, canonical URL and sitemap entry, and is produced by a single build command from
a single read of `awards.sqlite3`.

## Background

The explorer exists today as a separate three-file tool in `explorer/`: `build.py` (130 lines) reads `awards.sqlite3`,
folds laureates into one identity per Wikidata QID, scores each win as the prize family's prestige score / 100, and
bakes the whole result into `template.html` as one JSON blob, writing a self-contained `index.html` of 334 KB. It shares
nothing with the website — not the stylesheet, not the header, not the build.

The website (`website/build.py`, 1,314 lines) is a static generator: `read_database()` (`website/build.py:320-376`)
loads the same database once into `Ranking` and `AwardRecord` dataclasses, `create_site_plan()` (`website/build.py:640`)
turns them into a tuple of `PageJob`s, and `build_site()` (`website/build.py:1263-1287`) renders every job into a
staging directory, writes sitemaps and robots, then atomically promotes staging to `dist/`.

The two builds read the same database and emit into different places. The explorer is absent from the sitemap, has no
site navigation, and its `dist/` copy can silently go stale — which it had, by thirteen hours, before the current
session rebuilt it.

The decisive finding is that `AwardRecord` (`website/build.py:124-150`) already carries **every** field the explorer
payload needs — `year`, `category`, `prize_name`, `laureate_wikidata_qid`, `laureate_type`, `full_name`, `birth_country`,
`death_country`, `affiliation_country`, `citizenship_countries`, `birth_date`, `birth_year` — and `Ranking`
(`website/build.py:112-121`) carries `prize_name` and `score`, already ordered by score descending
(`website/build.py:330`). The payload can therefore be derived from the existing read with **no new SQL, no schema
change and no second database connection**.

## Assumptions

1. **(Load-bearing)** The explorer keeps its own visual identity — teal accent, own hero, own SVG charts — and does not
   adopt `website/static/style.css` typography or colour. Confirmed by the user. If this flips, the design collapses to
   a much larger CSS-merge task.
2. **(Load-bearing)** The explorer is **light-only**. Confirmed by the user. `website/static/style.css:14-23` defines a
   dark mode for the site; the explorer does not get one. A dark-mode visitor therefore sees dark site chrome above and
   below light explorer content. This seam is an accepted consequence, not a defect.
3. **(Load-bearing)** Both stylesheets define `--ink`, `--muted` and `--accent` on `:root` with different values
   (site `#262823 / #65675f / #526a55` at `style.css:1-12`; explorer `#1c1b1a / #6f6a63 / #0f766e` at
   `explorer/template.html:10-17`). The explorer's `<style>` renders inside `{% block head %}`, which base.html emits at
   line 18 — **after** the stylesheet link at line 16. Left at `:root`, the explorer's variables would win and repaint
   the site header, nav and footer teal on that page. All explorer custom properties MUST therefore be scoped to
   `.explorer`.
4. `explorer/template.html` contains no `{{`, `{%` or `{#` sequence, so it can be moved into Jinja verbatim apart from
   the deliberate edits below. Verified by grep across all 479 lines.
5. **(Load-bearing)** The `explorer/` directory is currently **untracked** in git (`?? datasets/explorer/`), so
   deleting `explorer/build.py` and `explorer/template.html` would destroy the only copy of the source being ported —
   with nothing to diff against if a porting regression surfaced later. The directory MUST therefore be committed
   before anything is deleted (task T0). After that commit the files are tracked, so `git mv` and `git rm` apply as
   normal per CLAUDE.md, and the removal becomes a revertible diff.
6. The test suite is `unittest`, not pytest — `tests/test_build_website.py:10,928`. `pytest` is neither installed nor
   declared, so the verification command is `uv run python -m unittest tests/test_build_website.py`. Baseline: 18
   tests passing.
7. The payload stays embedded in the page. No REST API, no runtime fetch — the explorer makes zero network calls. At
   2,372 laureates the page is 334 KB raw / 63 KB gzipped, of which the payload is 311 KB. The only site-wide cost of
   this change is the nav link: 42 bytes raw, 11-14 bytes gzipped per page, measured across 8,202 pages.
8. `Environment` uses `StrictUndefined` (`website/build.py:1180`), so every variable a template names must be supplied
   by **both** `_render_job()` and `render_error_page()`. Adding a nav link to base.html without updating both render
   paths breaks the 404 page.

## Scope

Approximately **+150 / −610 lines** across **9 files** (4 modified, 1 new, 1 moved, 3 deleted).

| File | Change | Size |
|---|---|---|
| `website/build.py` | modify — route constant, template registration, payload builder, page job, render kwargs | +85 |
| `website/templates/explorer.html` | **new** — ported from `explorer/template.html` | +470 |
| `website/templates/base.html` | modify — one nav link | +1 |
| `website/population.json` | **moved** from `explorer/population.json`, contents unchanged | 0 |
| `tests/test_build_website.py` | modify — payload fixture and route tests | +55 |
| `AGENTS.md` | modify — rewrite the stale `## data explorer` section (lines 75-90) | ~12 |
| `explorer/build.py` | **delete** — logic folded into `website/build.py` | −130 |
| `explorer/template.html` | **delete** — moved to `website/templates/explorer.html` | −479 |
| `explorer/index.html` | **delete** — generated artifact, superseded by `dist/explorer/index.html` | − |

## Design

```
BEFORE                                   AFTER
──────                                   ─────
awards.sqlite3                           awards.sqlite3
   │                                        │
   ├─► explorer/build.py                    └─► website/build.py
   │      read_rows()                              read_database()          ← one read
   │      + population.json                          │
   │      → explorer/index.html                      ├─► create_site_plan()
   │         (standalone, 334 KB,                    │      ├── prize / person / country jobs
   │          no nav, no sitemap)                    │      └── explorer job  ← new
   │                                                 │            └── explorer_payload()
   └─► website/build.py                              │                + population.json
          read_database()       ← second read        │
          → dist/               (explorer absent)    └─► dist/
                                                          ├── index.html …
                                                          ├── explorer/index.html  ← in sitemap
                                                          └── sitemap.xml
```

Rendering path for the new job, reusing the existing machinery unchanged:

```
create_site_plan()  ──► PageJob(template="explorer.html", route="/explorer/",
                                context={"payload": <json str>})
                              │
_render_job()  ────────►  explorer.html  {% extends "base.html" %}
                              │              ├── {% block head %}  scoped <style>
                              │              └── {% block content %} .explorer + <script>
                              ▼
                        dist/explorer/index.html
```

### Payload generation

A new `explorer_payload(rankings, records, population)` in `website/build.py` ports the body of
`explorer/build.py:56-116`, shrinking because it reuses what the website build already has:

- `_year_prefix(value, record_id)` (`website/build.py:295-301`) replaces the module-level `YEAR_PREFIX` regex and the
  hand-rolled year guard at `explorer/build.py:69-71`.
- `BuildFailure` (`website/build.py:108`) replaces the explorer's own exception class.
- `rankings` arrives already sorted by score descending, so the family index needs no re-sort.

The function MUST preserve the current payload shape exactly, so the ported JavaScript needs no change:

```python
{"families":   [{"name": str, "score": int}, ...],   # score-descending
 "countries":  [str, ...],                            # index-addressed
 "population": [int | None, ...],                     # aligned with countries
 "people":     [{"n","o","c","p","a","bc","dc","ac","cc","by"}, ...]}  # points-descending
```

Identity, scoring and country handling MUST match the current behaviour: laureates fold on
`laureate_wikidata_qid`, rows without a QID stay unmerged under a `row:{award_record_id}` key, points are
`round(sum(score / 100), 2)`, and `affiliation_country` / `citizenship_countries` split on `;` with each distinct
country counted once per person.

Serialization MUST keep the `<` escape from `explorer/build.py:111` —
`json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")` — so a `</script>` inside any
field cannot close the block early. This mirrors what `_structured_data()` already does at `website/build.py:480`.

### Template port

`website/templates/explorer.html` is `explorer/template.html` with these edits and no others:

| Current | Becomes | Why |
|---|---|---|
| `<!doctype html>` … `<body>` (lines 1-8, 109) | `{% extends "base.html" %}` | base.html owns the document shell |
| `<style>` block (lines 9-107) | `{% block head %}` with every selector scoped under `.explorer` | Assumption 3 |
| `* { box-sizing: border-box; }` (line 18) | deleted | `style.css:25-27` already sets it |
| `body { … }` + `main { … }` (lines 19-26) | merged into `.explorer { … }` | base.html supplies `<main>` at line 42 |
| `<main>` … `</main>` (lines 110, 199) | `<div class="explorer">` … `</div>` inside `{% block content %}` | avoids nested `<main>` |
| `<footer>` provenance note (lines 192-197) | `<p class="explorer-note">` | base.html supplies the site footer at lines 45-47 |
| "A standalone page, independent of the main awards website." (line 196) | **deleted** | It is no longer true. The page now carries the site header, nav, breadcrumbs, canonical URL and a sitemap entry; the sentence would contradict everything around it. The scoring and identity sentences (194-195) stay — they are still accurate provenance. |
| `__DATA__` (line 201) | `{{ payload\|safe }}` | autoescape is on (`build.py:1179`); the `<` escape already applied |
| `__GENERATED__` (line 195) | `{{ generated }}` | supplied via job context — see Wiring |
| `id="data"` (line 201) and its `getElementById("data")` (line 203) | `explorer-data` | avoids a collision with any future site-wide id |

All 275 lines of JavaScript (lines 202-477) move **verbatim except the data element id lookup** in the table above.
The chart code, sort logic, scoring and SVG helpers are untouched.

### Wiring

- `import datetime` added to the import block (`website/build.py:11-27`) — the module does not currently import it.
- `EXPLORER_ROUTE = "/explorer/"` beside the other route constants (`website/build.py:53-57`).
- `"explorer.html"` added to the `TEMPLATES` tuple (`website/build.py:38-52`) so `_environment()` validates it at
  startup (`website/build.py:1182-1183`).
- `POPULATION_FILE = SCRIPT_DIR / "population.json"`; `create_site_plan()` needs no new parameter because `SCRIPT_DIR`
  is already module-level.
- The job is appended in `create_site_plan()` before the duplicate-route check at `website/build.py:1104-1106`, built
  with the existing `_page()` helper (`website/build.py:379-387`):
  breadcrumbs `(Breadcrumb("Home", "/"), Breadcrumb("Explorer", None))`.
- **The `generated` stamp.** `create_site_plan()` (`website/build.py:640-642`) gains a `generated: str` parameter, and
  `build_site()` (`website/build.py:1263-1266`) computes it from the database file it was already handed:
  `datetime.datetime.fromtimestamp(database.stat().st_mtime, tz=datetime.UTC).date().isoformat()`. This is the data
  date, not the build date, so repeated builds of unchanged data stay byte-identical — the property
  `explorer/build.py` gained this session. It MUST reach the job context, or `StrictUndefined` fails the render
  (Assumption 8). Both call sites of `create_site_plan()` MUST be updated.
- `base.html:24-29` gains `<a href="{{ href(explorer_route) }}">Explorer</a>`.
- `explorer_route=EXPLORER_ROUTE` MUST be passed in **both** `_render_job()` (`website/build.py:1200-1202`) and
  `render_error_page()` (`website/build.py:1227-1229`) — see Assumption 8.

## Behavior / Acceptance

### Requirement: The explorer builds as part of the site — `build_site()` MUST emit it with no extra command

#### Scenario: single build produces the page
- WHEN `uv run website/build.py --base-url <url>` completes
- THEN `dist/explorer/index.html` exists
- AND it contains the site header, nav and footer from base.html
- AND `dist/sitemap.xml` contains the `/explorer/` route

#### Scenario: nav link resolves from every depth
- WHEN any page renders the site nav
- THEN the Explorer link is a correct relative path from that page's route
- AND `dist/404.html` renders without an undefined-variable error

### Requirement: The payload MUST reproduce the standalone build's output exactly

#### Scenario: exact fixture parity
- WHEN `explorer_payload()` runs against a small fixture dataset covering a QID merge across two prize families, a row
  with no QID, birth / death / affiliation / citizenship countries, a multi-country citizenship string, a missing
  birth year, and a `full_name` containing `</script>`
- THEN the returned dict equals the expected dict exactly — every key, every index, every score
- AND `population` is positionally aligned with `countries`
- AND points equal `round(sum(score / 100), 2)` for each person

#### Scenario: script-safe serialization
- WHEN the payload is serialized into the page
- THEN no literal `<` appears anywhere inside the `explorer-data` script block
- AND `JSON.parse` of that block round-trips to the original strings, `</script>` included

#### Scenario: parity with the retired script
- WHEN the payload is generated from the production database
- THEN `people`, `countries` and `families` have the same lengths and ordering the standalone build produced
  (2,372 people, 110 countries, 14 families as of this spec)

### Requirement: Explorer styling MUST NOT leak into site chrome

#### Scenario: custom properties stay scoped
- WHEN `/explorer/` renders
- THEN the site header and nav use the site accent `#526a55`, not the explorer teal `#0f766e`
- AND no explorer rule matches an element outside `.explorer`

### Requirement: Repo instructions MUST NOT reference deleted paths

#### Scenario: AGENTS.md matches reality
- WHEN the `## data explorer` section of `AGENTS.md` (lines 75-90) is read after implementation
- THEN it describes the explorer as a page of the website built by `website/build.py`, not a standalone tool
- AND it names no command or path that no longer exists — `uv run explorer/build.py`, `explorer/template.html`,
  `explorer/population.json`
- AND the country chart is described as "Laureates per million", the label the page now uses

## Out of scope

- Dark mode for the explorer (Assumption 2).
- Any change to chart logic, scoring, or the metrics themselves.
- Any change to `awards.sqlite3` or its schema.
- Build-time payload slicing (Assumption 7) — revisit only if the dataset grows roughly tenfold.
