# TODO — Refactor `create_site_plan` — 20260726

Spec: `docs/specs/datasets-build-refactor-20260726.md`. Read its **Assumptions** block before starting any task below; each
task assumes it.

## Rules for every task

- **All tasks touch one file, `website/build.py`. They are strictly SERIAL.** Do not parallelise. Run them in ID
  order.
- **Line numbers shift after every task.** The ranges below are from the pristine file at `4ad1cfd` and are for
  orientation only. Locate code by its anchor text (given in each task), never by absolute line number.
- **This is a pure code move.** Do not reword a string, reorder a dict literal, change a comparison, or "improve"
  anything you are moving. Copy the body verbatim; change only what the task explicitly lists.
- New functions are inserted **between `plan_subjects()` and `create_site_plan()`**, in task order, so the file reads
  top-down in build order.
- After each task: `python3 -m unittest tests.test_build_website` MUST print `Ran 22 tests … OK`, and
  `uv run ruff check website/build.py` MUST report **no error other than** the pre-existing
  `C901 create_site_plan is too complex`. That C901 error is expected to persist until T11 and its number MUST fall
  monotonically. If any new error appears (`E501` line >180 is the likely one), fix it before moving on.

---

### T0 — Capture the baseline

**Depends-on:** none
**Files:** none (read-only)

Steps → verify:

1. Confirm the tree is at the intended commit and the DB is untouched from here on. **`awards.sqlite3` MUST NOT be
   rebuilt or re-enriched for the duration of this refactor** — the byte-comparison is void if it changes.
2. Run:
   ```sh
   uv run website/build.py --base-url https://example.org/awards/ > /tmp/summary-before.txt
   rm -rf /tmp/dist-before && cp -a website/dist /tmp/dist-before
   python3 -m unittest tests.test_build_website
   uv run ruff check website/build.py
   ```
3. **Verify:** tests print `Ran 22 tests … OK`; ruff prints exactly one error,
   `C901 create_site_plan is too complex (55 > 18)`; `/tmp/dist-before` exists and is non-empty;
   `/tmp/summary-before.txt` contains one `website build complete …` line. Record the 55.

---

### T1 — Extract the three validators

**Depends-on:** T0
**Files:** `website/build.py` — source lines 1029-1082 (anchors: `ranking_by_qid: dict[str, Ranking] = {}`,
`live_names: dict[str, str] = {}`, `profiles_by_qid: dict[str, AffiliationProfile] = {}`)

Steps → verify:

1. Add `def index_rankings(rankings: list[Ranking]) -> dict[str, Ranking]:` holding lines 1029-1049 verbatim;
   `return ranking_by_qid`.
2. Add `def index_records(records: list[AwardRecord]) -> dict[str, list[AwardRecord]]:` holding lines 1051-1068
   verbatim; `return records_by_qid`. `live_names` stays as a **local** inside it — it is no longer returned.
3. Add `def index_profiles(profiles: Iterable[AffiliationProfile]) -> dict[str, AffiliationProfile]:` holding lines
   1076-1082 verbatim; `return profiles_by_qid`.
4. In `create_site_plan`, replace 1029-1082 with the three calls, and rewrite the cross-check (was 1070-1074) as:
   ```python
   if set(ranking_by_qid) != set(records_by_qid):
       raise BuildFailure("ranking rows do not match live awards")
   for qid, prize_records in records_by_qid.items():
       if ranking_by_qid[qid].prize_name != prize_records[0].prize_name:
           raise BuildFailure(f"ranking prize mismatch qid={qid}")
   ```
   (Equivalence argument: spec, Permitted incidental change 4.)
5. Every `BuildFailure` message MUST survive byte-identical — `tests/test_build_website.py:979-1015` asserts on the
   text.
6. **Verify:** 22 tests OK; ruff C901 number has dropped below 55.

---

### T2 — Add `PrizeLayout` and `layout_prize()`

**Depends-on:** T1
**Files:** `website/build.py` — insert dataclass after `class Subject` (source line 265); source lines 1093-1128
(anchor: `prize_records = records_by_qid[ranking.qid]`)

Steps → verify:

1. Add the `PrizeLayout` frozen dataclass exactly as given in the spec's **`PrizeLayout`** section, beside the other
   dataclasses.
2. Add `def layout_prize(ranking: Ranking, prize_records: list[AwardRecord]) -> PrizeLayout:` holding lines 1093-1128.
   Three required adaptations:
   - Compute `route = f"/{ranking.slug}/"` locally and use it in place of `prize_routes[ranking.qid]`
     (source line 1109). Equal by construction — source line 1086.
   - Build a **local** `record_routes: dict[str, str]` in place of `all_record_routes` (source line 1128).
   - Return `PrizeLayout(ranking, route, prize_records, routed_categories, category_slugs, year_routes, year_records, record_routes)`.
3. In `create_site_plan`, the prize loop becomes:
   ```python
   layout = layout_prize(ranking, records_by_qid[ranking.qid])
   all_record_routes.update(layout.record_routes)
   ```
   followed, for now, by the still-inline page-emitting code (T3-T4 move it). Rewrite that code's references to the
   old locals so it reads them off `layout` — or keep the old local names bound from `layout` fields as a temporary
   shim; either is fine as long as tests stay green.
4. **Verify:** 22 tests OK; C901 has dropped again.

---

### T3 — Extract `plan_category_pages()` and `plan_prize_page()`

**Depends-on:** T2
**Files:** `website/build.py` — source lines 1130-1236 (anchors: `category_links: list[tuple[str, str]] = []`,
`prize_title = f"{ranking.prize_name}: Winners by Year"`)

**This task contains the one trap in the refactor. Read the spec's "`category_links` has two consumers" section
before editing.**

Steps → verify:

1. Add `def _year_groups(group: list[AwardRecord], record_routes: dict[str, str]) -> tuple[tuple[str, tuple[tuple[AwardRecord, str], ...]], ...]:`
   holding the body of the `group_prize_records` closure (source lines 1208-1216), taking `record_routes` as a
   parameter instead of closing over `all_record_routes`.
2. Add `def plan_category_pages(layout: PrizeLayout) -> list[PageJob]:` holding source lines 1135-1172.
   - Return `[]` immediately when `not layout.routed_categories` (guard clause; replaces the `if routed_categories:`
     wrapper).
   - Iterate `sorted(layout.category_slugs)` in place of `sorted(categories)` — `categories` is not a layout field.
   - **Do NOT move `category_links` (source lines 1130-1134) here.** Drop those lines; they are rebuilt in step 3.
   - Drop the `category_page_count += 1` line (source 1172).
3. Add `def plan_prize_page(layout: PrizeLayout) -> PageJob:` holding source lines 1174-1182 (`direct_years`),
   1200-1206 (the recent window), and 1218-1236 (the page itself). It MUST rebuild `category_links` itself:
   ```python
   category_links = tuple(
       (category, layout.route + f"{layout.category_slugs[category]}/") for category in sorted(layout.category_slugs)
   ) if layout.routed_categories else ()
   ```
   and call `_year_groups(recent, layout.record_routes)` where the closure was called.
4. **Verify:** 22 tests OK. Then, because no test covers this, check by hand that a category-routed prize page still
   links its categories:
   ```sh
   uv run website/build.py --base-url https://example.org/awards/
   grep -c 'href="physics/"' website/dist/nobel-prize/index.html    # expect: 1, not 0
   ```

---

### T4 — Extract `_year_neighbours()` and `plan_year_pages()`

**Depends-on:** T3
**Files:** `website/build.py` — source lines 1184-1198 and 1238-1323 (anchors: `neighbours: dict[...]`,
`for (routed_category, year), grouped_records in year_records.items():`)

Steps → verify:

1. Add `def _year_neighbours(layout: PrizeLayout) -> dict[tuple[str | None, str], tuple[tuple[str, str] | None, tuple[str, str] | None]]:`
   holding source lines 1184-1198 verbatim; `return neighbours`.
2. Add `def plan_year_pages(layout: PrizeLayout, base_url: str, routes_by_laureate: dict[str, str]) -> list[PageJob]:`
   holding source lines 1238-1323 — **year pages and winner pages together, interleaved exactly as today**: one
   `year.html`, then that year's `winner.html` pages, then the next year. Do NOT extract a `_winner_page()` helper
   (spec: it would need seven arguments for one caller).
3. It MUST iterate `layout.year_records.items()` in insertion order. **Do not sort it.**
4. Call `_year_neighbours(layout)` once at the top.
5. Drop `year_page_count += 1` (source 1274) and `winner_page_count += 1` (source 1323).
6. The prize loop in `create_site_plan` is now exactly:
   ```python
   layout = layout_prize(ranking, records_by_qid[ranking.qid])
   record_routes.update(layout.record_routes)
   jobs.extend(plan_category_pages(layout))
   jobs.append(plan_prize_page(layout))
   jobs.extend(plan_year_pages(layout, base_url, routes_by_laureate))
   ```
   Remove any temporary shim left by T2.
7. **Verify:** 22 tests OK; C901 has dropped sharply.

---

### T5 — Extract `plan_person_pages()` and `plan_subject_pages()`

**Depends-on:** T4
**Files:** `website/build.py` — source lines 1332-1361 and 1366-1412 (anchors: `for person in people:`,
`"subjects.html"`)

Steps → verify:

1. Add `def plan_person_pages(people: list[Laureate], base_url: str) -> list[PageJob]:` holding source lines
   1332-1361 verbatim.
2. Add `def plan_subject_pages(subjects: list[Subject]) -> list[PageJob]:` holding source lines 1366-1412 — the
   `subjects.html` index page **first**, then per subject the `subject.html` and `subject_affiliations.html` pages,
   in that order.
3. **Verify:** 22 tests OK.

---

### T6 — Extract the three place/institution page families

**Depends-on:** T5
**Files:** `website/build.py` — source lines 1413-1517 (anchors: `recorded_affiliations = sum(`,
`"countries.html"`, `"affiliation_countries.html"`, `"affiliations.html"`)

Steps → verify:

1. Add `def plan_country_pages(countries: list[Place]) -> list[PageJob]:` holding source lines 1414-1441. It needs no
   `records` argument — the copy uses only `countries`. Apply permitted incidental change 2 here:
   `countries[0].people.__len__()` (source 1425) → `len(countries[0].people)`.
2. Add `def plan_affiliation_country_pages(affiliation_countries: list[AffiliationCountry], records: list[AwardRecord]) -> list[PageJob]:`
   holding source lines 1442-1479. It MUST compute `recorded_affiliation_countries` (source 1442) internally and
   use `len(records)` at source 1450/1456 — passing only `len(records)` would lose the first value.
3. Add `def plan_affiliation_pages(affiliations: list[Affiliation], records: list[AwardRecord]) -> list[PageJob]:`
   holding source line 1413 (`recorded_affiliations`) plus 1480-1517.
4. Preserve the emission order: countries index + country pages, then affiliation-countries index + pages, then
   affiliations index + pages.
5. **Verify:** 22 tests OK.

---

### T7 — Extract `plan_home_page()`, `plan_people_index()`, `plan_map_pages()`, `plan_explorer_page()`

**Depends-on:** T6
**Files:** `website/build.py` — source lines 1519-1628 (anchors: `year_prefixes = [`, `page_count = max(1,`,
`atlas_payload = map_json(`, `"explorer.html"`)

Steps → verify:

1. Add `def plan_home_page(rankings: list[Ranking], records: list[AwardRecord], people: list[Laureate], prize_routes: dict[str, str], ranking_by_qid: dict[str, Ranking], record_routes: dict[str, str]) -> PageJob:`
   holding source lines 1519-1565. `rankings` MUST be the **post-sort** list (source 1084) — source 1551 iterates it
   in score order. The local `recent` (source 1523) is now unambiguous; leave the name.
2. Add `def plan_people_index(people: list[Laureate]) -> list[PageJob]:` holding source lines 1567-1591.
3. Add `def plan_map_pages(records: list[AwardRecord]) -> list[PageJob]:` holding source lines 1593-1616 — the
   `/map/` page first, then one per `SUBJECTS` entry, sharing the single `atlas_payload`.
4. Add `def plan_explorer_page(rankings: list[Ranking], records: list[AwardRecord], routes_by_laureate: dict[str, str], generated: str) -> PageJob:`
   holding source lines 1618-1628.
5. **Verify:** 22 tests OK.

---

### T8 — Finish the composition root

**Depends-on:** T7
**Files:** `website/build.py` — `create_site_plan` body (anchors: `subject_counts: dict[str, int] = {}`,
`routes = [job.route for job in jobs]`)

Steps → verify:

1. Replace the subject-count loop (source 1326-1327) with
   `subject_counts = Counter(record.high_school_subject for record in records)`. `Counter` is already imported
   (source line 23) — do not add an import.
2. Hoist the `plan_places` / `plan_affiliation_countries` / `plan_subjects` calls (source 1363-1365) to sit directly
   after `plan_people`, above all the `jobs.extend(...)` calls. Safe per Assumption 4; job order is unchanged.
3. Delete `category_page_count`, `year_page_count`, `winner_page_count` (source 1087-1089) and derive the counts:
   ```python
   pages = Counter(job.template for job in jobs)
   ```
   feeding `pages["category.html"]`, `pages["year.html"]`, `pages["winner.html"]` into `SitePlan`, in the existing
   field order.
4. Rename `all_record_routes` → `record_routes` throughout the function.
5. The body MUST now match the spec's **Resulting `create_site_plan`** listing. Compare against it line by line.
6. **Verify:** 22 tests OK; `uv run ruff check website/build.py` prints **no errors at all** — C901 is finally clear.

---

### T9 — Full acceptance

**Depends-on:** T8
**Files:** none (read-only)

Steps → verify:

1. Run:
   ```sh
   uv run ruff check website/build.py
   python3 -m unittest tests.test_build_website
   uv run website/build.py --base-url https://example.org/awards/ > /tmp/summary-after.txt
   diff -r /tmp/dist-before website/dist
   diff /tmp/summary-before.txt /tmp/summary-after.txt
   git diff --stat -- tests/test_build_website.py
   ```
2. **Verify — all six MUST hold:**
   - ruff: `All checks passed`
   - tests: `Ran 22 tests … OK`
   - `diff -r`: **no output** — the acceptance gate
   - summary `diff`: **no output** — the only cover for `year_count`
   - `git diff --stat -- tests/…`: empty
   - `git diff --stat` otherwise shows `website/build.py` as the only source file changed
3. If `diff -r` reports any difference, identify the page family from the differing path and restore that family to
   its pre-refactor form before continuing. Do not "fix forward" by editing the template or the copy.

---

## Commit

One commit on a branch off the current head. Conventional commit, no tool attribution:

```
refactor: split create_site_plan into per-page-family planners

create_site_plan was 625 lines at C901 complexity 55 against the project
ceiling of 18 — the only ruff failure in the tree. Split it into three
input validators, a per-prize route layout, and one planner per page
family. Output is byte-identical: verified with diff -r over a full build.
```
