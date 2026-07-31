# TODO — Explorer integration into the awards website

Execution plan for `docs/specs/datasets-explorer-integration-20260726.md`. Each block is self-contained: a sub-agent runs one
block plus the spec's **Assumptions** section, with no other context.

Read the Assumptions block before starting any task. The load-bearing ones are 1 (explorer keeps its own look),
2 (light-only, no dark mode), 3 (CSS variables MUST be scoped to `.explorer`), 5 (`explorer/` must be committed by T0
before anything is deleted) and 8 (`StrictUndefined` — both render paths need every variable).

**T0 runs first and alone.** Until it lands, the explorer sources exist in exactly one place and are not in git.

```
T0 ──┬── T1 ──┬── T3 ──┐
     │        ├── T5 ──┼── T7
     ├── T2 ──┘        │
     ├── T4 ───────────┘
     └── T6 (independent)
```

---

## T0 — Commit the explorer sources before anything is deleted

**Depends-on:** none. **Serial — MUST complete before any other task.**

**Files:** `explorer/build.py`, `explorer/template.html`, `explorer/population.json`, `explorer/index.html`

**Why:** the whole directory is untracked. T7 deletes the builder and the template — the very source this change ports.
Without a commit there is no copy to restore and nothing to diff a suspected porting regression against. Committing
first turns an irreversible delete into a revertible diff, and makes `git mv` / `git rm` the correct tools downstream.

**Steps:**
1. Confirm the directory is untracked: `git status --porcelain explorer/` → `?? datasets/explorer/`.
2. Stage and commit the explorer exactly as it stands, before any integration edit:
   `git add explorer/ docs/specs/datasets-explorer-integration-20260726.md docs/specs/datasets-explorer-integration-todo-20260726.md`
   then commit as `chore: track the standalone explorer before folding it into the website`.
3. Do **not** modify any explorer file in this task. The commit must capture the working version — the one that
   currently builds a passing page — so it is a usable reference.

**Verify:**
- `git status --porcelain explorer/` → empty.
- `git log --oneline -1 -- explorer/build.py` → shows the new commit.
- `git show --stat HEAD` lists `explorer/build.py`, `explorer/template.html`, `explorer/population.json`.

---

## T1 — Payload generation and wiring in `website/build.py`

**Depends-on:** T0. **Serial** — sole owner of `website/build.py`.

**Files:** `website/build.py`

**Steps:**

1. Add `import datetime` to the import block (lines 11-27). It is not currently imported.
2. Add `EXPLORER_ROUTE = "/explorer/"` beside the other route constants (lines 53-57).
3. Add `POPULATION_FILE = SCRIPT_DIR / "population.json"` near the other module constants.
4. Add `"explorer.html"` to the `TEMPLATES` tuple (lines 38-52).
5. Add `load_population(country_names: list[str]) -> list[int | None]` — reads `POPULATION_FILE`, returns
   `[figures.get(name) for name in country_names]` so the result is positionally aligned with the country list.
   Port from `explorer/build.py:49-53`.
6. Add `explorer_payload(rankings: list[Ranking], records: list[AwardRecord], population_file: Path) -> dict`, porting
   `explorer/build.py:56-110`. It MUST:
   - Build `family_index` from `rankings` (already score-descending, `build.py:330` — do not re-sort).
   - Fold people on `laureate_wikidata_qid`, falling back to `f"row:{record.award_record_id}"` when the QID is blank.
   - Use the existing `_year_prefix(value, record_id)` (line 295) for year parsing — do **not** add a new regex.
   - Raise the existing `BuildFailure` (line 108) when a `prize_name` is missing from `award_ranking`.
   - Per person accumulate: `n` name, `o` 1 if `laureate_type == "Organization"` else 0, `a` sorted
     `[year, family_index, category]` triples, `bc`/`dc` first non-blank birth/death country index, `ac`/`cc` sorted
     sets of affiliation/citizenship country indices split on `;` and stripped, `by` first parseable birth year from
     `birth_date` then `birth_year`.
   - Score `p = round(sum(score / 100 for each award), 2)`, count `c = len(a)`.
   - Sort people by `(-p, -c, n)`.
   - Return `{"families": [{"name","score"}], "countries": [...], "population": [...], "people": [...]}`.
7. Add `explorer_json(payload: dict) -> str` returning
   `json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")`. The `<` escape is
   mandatory — it prevents a `</script>` inside any field from closing the block early, mirroring line 480.
8. Change `create_site_plan()` (line 640) to take a new `generated: str` parameter.
9. Inside `create_site_plan()`, before the duplicate-route check at lines 1104-1106, append the explorer job using the
   existing `_page()` helper (lines 379-387):
   - template `"explorer.html"`, route `EXPLORER_ROUTE`
   - title and description of your choosing, description within `DESCRIPTION_LIMIT`
   - breadcrumbs `(Breadcrumb("Home", "/"), Breadcrumb("Explorer", None))`
   - context `payload=explorer_json(...)`, `generated=generated`
10. In `build_site()` (lines 1263-1266), compute
    `generated = datetime.datetime.fromtimestamp(database.stat().st_mtime, tz=datetime.UTC).date().isoformat()` and
    pass it to `create_site_plan()`. Use the timezone-aware form — the naive `datetime.date.fromtimestamp()` trips
    ruff's `DTZ012`.
11. Add `explorer_route=EXPLORER_ROUTE` to the render kwargs in **both** `_render_job()` (lines 1200-1202) **and**
    `render_error_page()` (lines 1227-1229). Missing the second breaks `404.html` under `StrictUndefined`.

**Verify:**
- `ruff check website/build.py` → clean, `DTZ012` included.
- `uv run python -c` is not permitted; verify via the test suite in T5 and the build in T7.

---

## T2 — Port the template to `website/templates/explorer.html`

**Depends-on:** T0. **Parallel-safe** — new file, no other task touches it.

**Files:** `website/templates/explorer.html` (new), source `explorer/template.html` (479 lines, read-only here)

**Steps:**

1. Create the file with `{% extends "base.html" %}`.
2. `{% block head %}` — move the `<style>` block (source lines 9-107) with every selector scoped under `.explorer`:
   - Delete `* { box-sizing: border-box; }` (line 18) — `static/style.css:25-27` already sets it globally.
   - `:root { --ink … --bg }` (lines 10-17) becomes `.explorer { --ink … --bg }`. **This is load-bearing** — left at
     `:root` the explorer's teal `--accent: #0f766e` overrides the site's `#526a55` and repaints the site header and
     nav on this page.
   - Merge `body {…}` (19-25) and `main {…}` (26) into the single `.explorer {…}` rule.
   - Prefix every remaining selector with `.explorer ` — `.eyebrow`, `h1`, `h2`, `.lede`, `.hero`, `.stats`, `section`,
     `.section-note`, `.board-tools`, `#q`, `#hits`, `table`, `thead th`, `th button`, `tbody tr.person`, `td`,
     `.badge`, `tr.detail`, `figure`, `svg`, `.axis`, `.grid`, `.bar`, `.bar-label`, `.bar-value`, `.dot`,
     `.chart-select`, and the `@media (max-width: 640px)` rules at lines 102-106.
   - `footer {…}` (98-101) becomes `.explorer .explorer-note {…}`.
   - Add no dark-mode block (Assumption 2).
3. `{% block content %}` — move the body (source lines 110-199) wrapped in `<div class="explorer">`:
   - Drop the `<main>` / `</main>` tags (110, 199) — base.html supplies `<main>` at line 42.
   - Keep the `<header class="hero">` and all six `<section>` elements verbatim.
   - The `<footer>` provenance note (192-197) becomes `<p class="explorer-note">`, with `__GENERATED__` replaced by
     `{{ generated }}`.
   - **Delete the sentence "A standalone page, independent of the main awards website." (line 196).** It is no longer
     true — the page now carries the site header, nav, breadcrumbs, canonical URL and a sitemap entry, and the sentence
     would contradict all of them. Keep the scoring and identity sentences (194-195); they remain accurate.
4. Still inside `{% block content %}`, after the closing `</div>`, add the data block and script:
   - `<script id="explorer-data" type="application/json">{{ payload|safe }}</script>` — `|safe` is required because
     autoescape is on (line 1179); the payload already has `<` escaped by T1.
   - The `<script>` body: source lines 202-477 **verbatim**, with exactly one edit —
     `document.getElementById("data")` (line 203) becomes `document.getElementById("explorer-data")`.

**Verify:**
- The file contains no `<!doctype`, `<html>`, `<head>`, `<body>`, `<main>` or `<footer>` tag.
- `grep -c ':root' website/templates/explorer.html` → `0`.
- Every CSS rule in the file is prefixed with `.explorer`.

---

## T3 — Add the nav link

**Depends-on:** T1 (needs `explorer_route` passed to both render paths). **Files:** `website/templates/base.html`

**Steps:**
1. In the `<nav class="site-nav">` block (lines 24-29), add `<a href="{{ href(explorer_route) }}">Explorer</a>` after
   the Institutions link.

**Verify:** `dist/404.html` renders without an undefined-variable error (covered by T7's build).

---

## T4 — Move the population snapshot

**Depends-on:** T0. **Parallel-safe.**

**Files:** `explorer/population.json` → `website/population.json`

**Steps:**
1. `git mv explorer/population.json website/population.json`. T0 has made the file tracked, so `git mv` is now the
   correct tool per CLAUDE.md — and the move stays visible in history.
2. Do not edit the contents. It has 106 entries and the `Türkiye` duplicate key was already removed this session.

**Verify:**
- `jq -e '.population.Turkey and (.population | length == 106)' website/population.json` → true.
- `git status --porcelain` shows the move as a rename, not an add plus delete.

---

## T5 — Tests

**Depends-on:** T1, T2. **Files:** `tests/test_build_website.py`

**Steps:**
1. Add an exact-fixture test for `explorer_payload()`. Build a small in-memory list of `Ranking` and `AwardRecord`
   objects covering: one laureate merged across two prize families by QID; one row with a blank QID; birth, death,
   affiliation and citizenship countries; a multi-country citizenship string with `;` separators; a person with no
   parseable birth year; and a `full_name` containing `</script>`. Assert the returned dict **equals** the expected
   dict exactly — keys, indices, ordering and scores.
2. Assert `population` is positionally aligned with `countries`.
3. Assert points equal `round(sum(score / 100), 2)` per person.
4. Add a serialization test: `explorer_json()` output contains no literal `<`, and `json.loads()` of it round-trips
   the `</script>` name unchanged.
5. Add a route test: the plan contains a job with route `/explorer/` and template `explorer.html`.

**Verify:** `uv run python -m unittest tests/test_build_website.py` → all pass. The suite is `unittest`, not pytest —
pytest is not installed and not declared. The baseline is **18 tests passing**; this task adds to that count.

---

## T6 — Update `AGENTS.md`

**Depends-on:** none. **Parallel-safe.** **Files:** `AGENTS.md` lines 75-90

**Steps:**
1. Rewrite the `## data explorer` section. It currently describes a standalone tool and names three paths that this
   change deletes or moves: `uv run explorer/build.py` (line 80), `explorer/build.py` / `explorer/template.html`
   (lines 82-83), and `explorer/population.json` (line 90).
2. Replace with: the explorer is a page of the website at `/explorer/`, built by `website/build.py` along with every
   other page; its template is `website/templates/explorer.html` and its population snapshot is
   `website/population.json`.
3. Line 90 also calls the country chart **"Births per million people"**. That label no longer exists — it is
   **"Laureates per million"**, and it counts each person once regardless of award count. Fix this wording too.

**Verify:** `grep -c 'explorer/build.py\|explorer/template.html\|explorer/population.json\|Births per million' AGENTS.md`
→ `0`.

---

## T7 — Build, verify, and remove the standalone tool

**Depends-on:** T0, T1, T2, T3, T4, T5, T6. **Serial** — final gate.

**Files:** deletes `explorer/build.py`, `explorer/template.html`, `explorer/index.html`

**Steps:**
1. Run the site build: `uv run website/build.py --base-url <url>`.
2. Confirm **every** check below passes. Do not proceed to step 3 on a partial pass.
3. Only then `git rm explorer/build.py explorer/template.html explorer/index.html`. T0 made these tracked, so this is
   a revertible diff rather than a destructive delete; the directory should end up empty and can be removed.
   If any check in step 2 failed, stop and report — the originals are still in place and still building.

**Verify:**
- `dist/explorer/index.html` exists and contains the site header, nav and footer.
- It contains `Laureates per million` and the six section headings.
- `dist/sitemap.xml` contains `/explorer/`.
- `dist/404.html` exists and rendered without error.
- Extract the `explorer-data` block: it parses as JSON, has 2,372 people / 110 countries / 14 families, and contains
  no literal `<`.
- Extract the page script and run `node --check` on it → clean.
- The site accent `#526a55` still applies to the header on `/explorer/`; the teal `#0f766e` appears only inside
  `.explorer`.
- Run the build twice; `dist/explorer/index.html` is byte-identical across both runs.
