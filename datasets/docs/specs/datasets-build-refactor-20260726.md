# Refactor `create_site_plan` — 20260726

## Goals

Break `create_site_plan()` (`website/build.py:1019-1643`, 625 lines) into a short composition root plus one small
function per page family, clearing the repo's only lint failure. The rendered site MUST be byte-identical before and
after: this is a pure refactor.

## Background

`website/build.py` is 1851 lines and builds the whole static site from `awards.sqlite3`. Its shape is already good in
places — small pure helpers (`_clamp`, `_names`, `_year_span`, `_by_motivation`), and data planners that return
domain objects (`plan_places`, `plan_people`, `plan_subjects`, `plan_affiliation_countries`). Every other top-level
function in the file is at most 90 lines.

`create_site_plan()` is the exception, and it is not merely a style complaint — **it fails the repo's own gate**:

```
$ uv run ruff check website/build.py
C901 `create_site_plan` is too complex (55 > 18)
Found 1 error.
```

`ruff.toml` sets `extend-select = ["C901"]` with `max-complexity = 18`, added at `4ad1cfd`. `create_site_plan` scores
**55** — three times the ceiling — and is the single reason `ruff check` is red across the project. Clearing that is
this refactor.

The complexity is structural. One body holds: four input validators, per-prize route allocation, page construction
for thirteen distinct page families, three manually maintained counters, a closure redefined once per prize
(`group_prize_records`, `website/build.py:1208-1216`), and the final `SitePlan` assembly. Two different locals are
both named `recent` (`website/build.py:1206` and `1523`). The function has a clear phase structure already —
validate, allocate routes, emit pages, assemble — but nothing in the code marks the boundaries.

The safety net is strong: `tests/test_build_website.py` is 1228 lines / 22 tests, most of which drive the full
`build_site()` against a temporary SQLite database and assert on rendered HTML, routes, sitemaps, and metadata. All 22
pass at `4ad1cfd`. That is what makes a mechanical refactor of this size safe in one pass.

Prior specs that shaped this function: `docs/specs/datasets-website-cleanup-20260725.md`,
`docs/specs/datasets-explorer-integration-20260726.md`, `docs/specs/datasets-subject-taxonomy-20260726.md`,
`docs/specs/website-map-integration-20260726.md`. A pending spec, `docs/specs/datasets-multilingual-20260726.md`, plans to
parameterise this function by language — that work gets materially easier against small functions, and this refactor
is a prerequisite worth doing first.

## Assumptions

1. **Load-bearing.** This is a behaviour-preserving refactor. No route, no page, no title, no description, no
   structured-data payload, and no log line changes. The verification is a byte-level `diff -r` of two builds.
2. **Load-bearing.** `create_site_plan()` keeps its exact signature and return type.
   `tests/test_build_website.py:213` and `:299` call it directly with four positional arguments.
3. Job order within `SitePlan.jobs` has **no effect on output bytes** — `write_sitemaps()` sorts its routes
   (`website/build.py:1659`), rendering is already order-nondeterministic through
   `ThreadPoolExecutor(max_workers=8)` (`website/build.py:1809`), and the duplicate-route check is set-based
   (`website/build.py:1631`). Order is preserved anyway: it costs nothing and keeps the decomposition mechanical.
4. `plan_places()` (`website/build.py:758-847`) is pure — it reads `people` and `records` and returns new lists,
   mutating neither. Verified by reading; `plan_affiliation_countries()` and `plan_subjects()` likewise. Their calls
   MAY therefore be hoisted above the person-page emission.
5. **Load-bearing.** The templates `category.html`, `year.html`, and `winner.html` are each emitted at exactly one
   site (`website/build.py:1155`, `1260`, `1297`), and each manual counter increments on the statement immediately
   after its `jobs.append`, at the same nesting depth, with no intervening `continue` or conditional
   (`website/build.py:1172`, `1274`, `1323`). Strict 1:1. The counters are therefore derivable from the finished job
   list, and `Counter[missing]` returns `0`, matching the `= 0` initialisers.
6. **Load-bearing.** Within one prize's page family, every `all_record_routes` lookup resolves to a record of that
   same prize — `website/build.py:1141`, `1212`, `1215`, `1269`, `1298`, `1306`, `1317` all read from `year_records`
   or `prize_records`. Verified: no cross-prize lookup exists. Per-prize route dicts therefore suffice inside the
   loop, and merging them is collision-free because record IDs are globally unique (`website/build.py:1055-1057`).
7. No public API is added. Every new function is internal to `build.py`; nothing imports `build` except
   `tests/test_build_website.py`.
8. No new tests are required — the existing 22 are the contract. Tests are touched only if the refactor breaks them,
   which per Assumption 1 it must not.

## Scope

| File | Change | LOC |
| --- | --- | --- |
| `website/build.py` | `create_site_plan` 625 → ~60 lines; 18 new functions + 1 dataclass carrying the moved code | ~625 moved, ~+45 net |
| `tests/test_build_website.py` | none expected | 0 |

One file. No new dependencies, no new module. The file grows by roughly 45 lines (1851 → ~1896) — the cost of 19
signatures, returns, and docstrings, paid for by removing the manual counters, the per-prize closure, and the name
collisions.

## Design

### Naming rule

The file already distinguishes two kinds of planner. Make it explicit and keep it:

- `plan_<thing>()` returns **domain data** — the four existing ones (`plan_people` → `list[Laureate]`) are unchanged.
- `plan_<thing>_pages()` returns **`list[PageJob]`**; singular `plan_<thing>_page()` returns one `PageJob`.

The paginated A–Z index is `plan_people_index()`, not `plan_people_pages()`, to stay clearly distinct from the
existing `plan_people()`. Functions prefixed `_` are helpers with exactly one caller.

There is no line-count rule. `C901 max-complexity = 18` is the enforced budget and it is the right one: it measures
branching, not length. A long function of straight-line `_page(...)` construction is fine — splitting it buys
nothing.

### Structure

```
create_site_plan()  ── 625 lines, C901 = 55 ──►  create_site_plan()  ── ~60 lines, C901 ≈ 7
                                                     │
   ┌─────────────────────────────────────────────────┼──────────────────────────────────┐
   │ 1. validate                                     │                                  │
   │    index_rankings()      qid → Ranking, slug/score/url contract                    │
   │    index_records()       qid → [AwardRecord], id/name/subject/year                 │
   │    index_profiles()      qid → AffiliationProfile                                  │
   │    (cross-check ranking set == live award set stays inline, 5 lines)               │
   ├─────────────────────────────────────────────────┼──────────────────────────────────┤
   │ 2. per prize, in score order                    │                                  │
   │    layout_prize(ranking, records) ──► PrizeLayout                                  │
   │      · routed_categories?  category_slugs  year_routes                             │
   │      · year_records        record_routes (this prize only)                         │
   │                                                 │                                  │
   │    plan_category_pages(layout)       ──► [category.html …]                         │
   │    plan_prize_page(layout)           ──►  prize.html    └─ _year_groups()          │
   │    plan_year_pages(layout, …)        ──► [year.html, winner.html …]                │
   │                                                         └─ _year_neighbours()      │
   ├─────────────────────────────────────────────────┼──────────────────────────────────┤
   │ 3. site-wide, using the merged route table                                         │
   │    plan_person_pages()          plan_subject_pages()                               │
   │    plan_country_pages()         plan_affiliation_country_pages()                   │
   │    plan_affiliation_pages()     plan_home_page()                                   │
   │    plan_people_index()          plan_map_pages()      plan_explorer_page()         │
   ├─────────────────────────────────────────────────┼──────────────────────────────────┤
   │ 4. assemble: duplicate-route check, counts by template, SitePlan                   │
   └────────────────────────────────────────────────────────────────────────────────────┘
```

### `PrizeLayout`

The per-prize loop currently carries six locals across 230 lines. One frozen dataclass replaces them and becomes the
single argument to the three per-prize planners. Insert after `Subject` and before `SitePlan`
(`website/build.py:265`), with the other dataclasses:

```python
@dataclass(frozen=True, slots=True)
class PrizeLayout:
    """Every route one prize owns, allocated before any of its pages are built."""
    ranking: Ranking
    route: str
    records: list[AwardRecord]
    routed_categories: bool
    category_slugs: dict[str, str]
    year_routes: dict[tuple[str | None, str], str]
    year_records: dict[tuple[str | None, str], list[AwardRecord]]
    record_routes: dict[str, str]
```

Three details the implementation MUST get right:

- **`route` is computed inside `layout_prize()`** as `f"/{ranking.slug}/"`. That is exactly how `prize_routes` is
  built (`website/build.py:1086`), so `layout_prize()` needs no `prize_routes` argument even though the moved code
  reads it at `website/build.py:1109`.
- **`categories` is not a field.** `plan_category_pages()` MUST iterate `sorted(layout.category_slugs)` in place of
  `sorted(categories)` (`website/build.py:1132`). `_category_slugs()` (`website/build.py:570-578`) keys its result on
  every member of `categories`, so the two are equal whenever `routed_categories` is true — the only branch that
  reaches that line.
- **`routed_categories`** stays a named field even though `bool(category_slugs)` is equivalent
  (`website/build.py:1097`). A named boolean beats a truthiness check.

`layout_prize()` returns its own `record_routes` rather than writing into a shared dict (Assumption 6); the caller
merges with `record_routes.update(layout.record_routes)`. Every per-prize planner is then a pure function of its
layout.

### `category_links` has two consumers — the one trap in this refactor

`category_links` is built inside the category-page block (`website/build.py:1130-1134`) but consumed by the **prize**
page (`website/build.py:1231`), not by the category pages. A naive "move 1130-1172 into `plan_category_pages()`"
silently drops it: `plan_prize_page()` would pass an empty tuple, `website/templates/prize.html:30` would render no
`<li>`, and **every category-routed prize page would lose its entire category navigation**. `StrictUndefined` does
not catch this — the key is still present, just empty. No test covers it
(`tests/test_build_website.py:384-386` asserts the Japan Prize's *year* links; `:399-401` asserts the category page
body, not the prize page's links to it). Only `diff -r` would catch it.

`plan_prize_page()` MUST therefore recompute it from the layout:

```python
category_links = tuple(
    (category, layout.route + f"{layout.category_slugs[category]}/") for category in sorted(layout.category_slugs)
) if layout.routed_categories else ()
```

This keeps `plan_category_pages()` returning a plain `list[PageJob]` instead of a `(jobs, links)` tuple.

### Line-by-line destination map

| Current lines | Content | Destination |
| --- | --- | --- |
| 1019-1025 | signature | stays inline, unchanged (Assumption 2) |
| 1026-1027 | empty-input guard | stays inline |
| 1029-1049 | ranking validation → `ranking_by_qid` | `index_rankings()` |
| 1051-1068 | record validation → `records_by_qid` (`live_names` becomes local to the validator) | `index_records()` |
| 1070-1074 | ranking set ↔ live award set cross-check | stays inline (reads `records_by_qid[qid][0].prize_name`) |
| 1076-1082 | affiliation profile validation | `index_profiles()` |
| 1084-1091 | sort by score, `prize_routes`, counters, `routes_by_laureate` | stays inline; the three counters are deleted |
| 1093-1128 | routed categories, category slugs, year routes, winner routes | `layout_prize()` |
| 1130-1134 | `category_links` | **recomputed in `plan_prize_page()`** — see above |
| 1135-1172 | category pages | `plan_category_pages()` |
| 1174-1182 | `direct_years` | `plan_prize_page()` |
| 1184-1198 | adjacent-year map | `_year_neighbours()` |
| 1200-1216 | recent-window records, `group_prize_records` closure | `plan_prize_page()`; closure → `_year_groups()` |
| 1218-1236 | prize page | `plan_prize_page()` |
| 1238-1323 | year pages and, interleaved, their winner pages | `plan_year_pages()` |
| 1325-1330 | subject counts and display order | stays inline (via `Counter`) |
| 1331 | `plan_people()` call | stays inline |
| 1332-1361 | person pages | `plan_person_pages()` |
| 1363-1365 | `plan_places`, `plan_affiliation_countries`, `plan_subjects` calls | stays inline, hoisted above the emits |
| 1366-1412 | subjects index + subject + subject-institutions pages | `plan_subject_pages()` |
| 1413-1441 | `recorded_affiliations`; countries index + country pages | counter → `plan_affiliation_pages()`; pages → `plan_country_pages()` |
| 1442-1479 | `recorded_affiliation_countries`; institutions-by-country pages | `plan_affiliation_country_pages()` |
| 1480-1517 | affiliations index + affiliation pages | `plan_affiliation_pages()` |
| 1519-1565 | homepage | `plan_home_page()` |
| 1567-1591 | people A–Z index, paginated | `plan_people_index()` |
| 1593-1616 | map pages | `plan_map_pages()` |
| 1618-1628 | explorer page | `plan_explorer_page()` |
| 1630-1643 | duplicate-route check, `SitePlan` | stays inline; counts derived from templates |

Everything not listed is blank lines. New functions are inserted between `plan_subjects()` (ends
`website/build.py:1016`) and `create_site_plan()` (`website/build.py:1019`), in the order of the table, so the file
reads top-down in build order.

**Winner pages stay inside `plan_year_pages()`.** Extracting a `_winner_page()` helper would need seven arguments
(`record`, `layout`, `routed_category`, the year route, `ordered_group` for co-laureates, `base_url`,
`routes_by_laureate`) for a single caller, and would make `plan_year_pages` a pass-through for `base_url` and
`routes_by_laureate`, which nothing else in it uses. Merged, the function measures C901 = 6 against a ceiling of 18
and is ~85 lines of straight-line construction. It MUST iterate `layout.year_records.items()` in insertion order and
MUST NOT sort it — it emits one `year.html` followed immediately by that year's `winner.html` pages, the existing
interleaving.

### Resulting `create_site_plan`

```python
def create_site_plan(
    rankings: list[Ranking],
    records: list[AwardRecord],
    base_url: str,
    generated: str,
    profiles: Iterable[AffiliationProfile] = (),
) -> SitePlan:
    if not rankings or not records:
        raise BuildFailure("ranking or awards table is empty")

    ranking_by_qid = index_rankings(rankings)
    records_by_qid = index_records(records)
    profiles_by_qid = index_profiles(profiles)
    if set(ranking_by_qid) != set(records_by_qid):
        raise BuildFailure("ranking rows do not match live awards")
    for qid, prize_records in records_by_qid.items():
        if ranking_by_qid[qid].prize_name != prize_records[0].prize_name:
            raise BuildFailure(f"ranking prize mismatch qid={qid}")

    rankings = sorted(rankings, key=lambda ranking: ranking.score, reverse=True)
    routes_by_laureate = person_routes(records)
    prize_routes = {ranking.qid: f"/{ranking.slug}/" for ranking in rankings}
    record_routes: dict[str, str] = {}
    jobs: list[PageJob] = []
    for ranking in rankings:
        layout = layout_prize(ranking, records_by_qid[ranking.qid])
        record_routes.update(layout.record_routes)
        jobs.extend(plan_category_pages(layout))
        jobs.append(plan_prize_page(layout))
        jobs.extend(plan_year_pages(layout, base_url, routes_by_laureate))

    subject_counts = Counter(record.high_school_subject for record in records)
    subject_order = {name: index for index, name in enumerate(sorted(subject_counts, key=lambda subject: (-subject_counts[subject], subject)))}
    people = plan_people(records, routes_by_laureate, record_routes, subject_order)
    countries, affiliations = plan_places(people, records, record_routes, profiles_by_qid)
    affiliation_countries = plan_affiliation_countries(affiliations)
    subjects = plan_subjects(people, subject_counts, affiliations)

    jobs.extend(plan_person_pages(people, base_url))
    jobs.extend(plan_subject_pages(subjects))
    jobs.extend(plan_country_pages(countries))
    jobs.extend(plan_affiliation_country_pages(affiliation_countries, records))
    jobs.extend(plan_affiliation_pages(affiliations, records))
    jobs.append(plan_home_page(rankings, records, people, prize_routes, ranking_by_qid, record_routes))
    jobs.extend(plan_people_index(people))
    jobs.extend(plan_map_pages(records))
    jobs.append(plan_explorer_page(rankings, records, routes_by_laureate, generated))

    routes = [job.route for job in jobs]
    if len(routes) != len(set(routes)):
        raise BuildFailure("duplicate public route")
    pages = Counter(job.template for job in jobs)
    return SitePlan(
        tuple(jobs), len(rankings), pages["category.html"], pages["year.html"], pages["winner.html"],
        len(records), len(people), len(countries), len(subjects),
    )
```

`plan_home_page()` and `plan_explorer_page()` MUST receive the **post-sort** `rankings` rebound at
`website/build.py:1084` — `website/build.py:1551` iterates it in score order. The body above does this.

`all_record_routes` is renamed to `record_routes`: the `all_` prefix distinguished it from per-prize locals that no
longer share this scope, and it matches the parameter name `plan_places()` and `plan_people()` already use.

### Permitted incidental changes

The only changes that are not pure code movement. Each is behaviour-identical.

1. The three counters (`website/build.py:1087-1089`, `1172`, `1274`, `1323`) are deleted; counts derive from
   `Counter(job.template for job in jobs)` (Assumption 5).
2. `countries[0].people.__len__()` (`website/build.py:1425`) becomes `len(countries[0].people)`.
3. The subject-count loop (`website/build.py:1326-1327`) becomes
   `Counter(record.high_school_subject for record in records)`. `Counter` is already imported
   (`website/build.py:23`) and is a `dict[str, int]`; it is consumed only through
   `sorted(..., key=lambda s: (-subject_counts[s], s))` — a total order over unique names — so iteration order is
   irrelevant.
4. `index_records()` returns one dict, not two. `live_names` becomes a local: `live_names[qid]` is set at
   `website/build.py:1065` and `records_by_qid[qid]` appended at `:1068` in the same iteration, and the `:1066`
   consistency guard makes it uniform, so `live_names[qid] == records_by_qid[qid][0].prize_name` always. The
   cross-check's first-failing qid and message are unchanged.
5. The `group_prize_records` closure (`website/build.py:1208-1216`), redefined once per prize, becomes a
   module-level `_year_groups(group, record_routes)`.
6. `all_record_routes` → `record_routes`.

### Explicitly out of scope

- `_year_prefix()` is called repeatedly on the same values (`website/build.py:1139`, `1177`, `1188`, `1202`, `1206`,
  `1520`, `1526`, `1528`). Caching it is a performance change, not a clarity change. Leave it.
- `plan_places()` returning a two-tuple and doing two jobs — a known wart from
  `docs/specs/datasets-country-institutions-cleanup-20260726.md`. Not this spec.
- `read_database()`, `_render_job()`, `build_site()`, `write_sitemaps()`, and the map/explorer payload builders. All
  are at most 90 lines and are not touched.
- No template, no CSS, no SQL, no CLI change.

## Requirements

### Requirement: `ruff check` MUST pass

#### Scenario: the project's only lint failure is cleared
- WHEN `uv run ruff check website/build.py` runs after the refactor
- THEN it MUST report no errors
- AND no function MUST exceed `max-complexity = 18` — `create_site_plan` is at 55 today

### Requirement: Output is byte-identical — the refactor MUST NOT change the rendered site

#### Scenario: full build against the live database
- WHEN `uv run website/build.py --base-url https://example.org/awards/` runs against `awards.sqlite3` before the
  refactor, and `website/dist` is copied aside as a reference
- AND the same command runs after the refactor
- THEN `diff -r /tmp/dist-before website/dist` MUST report no differences
- AND `awards.sqlite3` MUST NOT be rebuilt or re-enriched between the two builds, or the comparison is void

#### Scenario: the build's summary line is unchanged
- WHEN `main()` prints its `website build complete …` line after the refactor
- THEN every count — `prizes`, `categories`, `year_pages`, `winner_pages`, `people`, `countries`, `subjects`,
  `recipients`, `sitemap_urls`, `generated_pages` — MUST equal the pre-refactor value
- AND this is the ONLY check covering `year_count`: `dist` never contains it and
  `tests/test_build_website.py:375` asserts only `prize_count`, `category_count`, and `winner_count`

### Requirement: The existing test suite MUST pass unmodified

#### Scenario: full suite
- WHEN `python3 -m unittest tests.test_build_website` runs after the refactor
- THEN all 22 tests MUST pass
- AND `git diff --stat -- tests/test_build_website.py` MUST be empty

### Requirement: Every validation failure MUST still fail the build with the same message

#### Scenario: an invalid subject
- WHEN a record carries a `high_school_subject` outside `SUBJECTS`
- THEN `index_records()` MUST raise `BuildFailure(f"invalid subject record_id={…}")`, exactly as
  `website/build.py:1063` does today
- AND every other `BuildFailure` string moved out of `create_site_plan()` MUST be byte-identical, since
  `tests/test_build_website.py:979-1015` asserts on the text

## Verification

Run in order. Step 1 MUST be captured before any edit.

```sh
# 1. reference build and summary, before touching anything
uv run website/build.py --base-url https://example.org/awards/ > /tmp/summary-before.txt
rm -rf /tmp/dist-before && cp -a website/dist /tmp/dist-before
python3 -m unittest tests.test_build_website          # expect: Ran 22 tests … OK

# 2. after the refactor
uv run ruff check website/build.py                    # expect: All checks passed (was: C901 55 > 18)
python3 -m unittest tests.test_build_website          # expect: Ran 22 tests … OK
uv run website/build.py --base-url https://example.org/awards/ > /tmp/summary-after.txt
diff -r /tmp/dist-before website/dist                 # expect: no output  <- the acceptance gate
diff /tmp/summary-before.txt /tmp/summary-after.txt   # expect: no output  <- covers year_count

# 3. nothing outside build.py moved
git diff --stat -- tests/test_build_website.py        # expect: empty
```

`diff -r` returning empty is the acceptance gate, and it is trustworthy: `_promote()`
(`website/build.py:1776-1796`) renames `dist` aside and moves staging in whole, so `website/dist` is a fresh tree
every build and stale files cannot mask a dropped page. It is also the **only** gate that catches the `category_links`
trap, so the reference build MUST come from a database containing a category-routed prize with more than one category
— the live `awards.sqlite3` does. Running the tests as well is not redundant: `diff -r` covers only the happy path,
while the tests are the sole cover for the moved `BuildFailure` messages.

If `diff -r` reports a difference, the refactor changed behaviour; the offending page family goes back to its
original form before proceeding.
