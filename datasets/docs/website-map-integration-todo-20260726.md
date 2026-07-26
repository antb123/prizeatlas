## T0 — Protect current data state

**ID:** T0

**Goal:** Confirm the map integration does not absorb or lose the current database corrections.

**Depends-on:** none

**Files:** `awards.sqlite3` (read-only inspection; no integration edit)

**Assumptions:** 1, 5

**Steps → verify:**

1. Record `git status --short awards.sqlite3` and verify the file is already modified before integration work.
2. Query the UC Berkeley and UCSF affiliation QIDs and confirm their verified coordinates remain `-122.2583,37.8719` and `-122.4581,37.7628`.
3. Do not stage `awards.sqlite3` in the map integration commit.
4. After all implementation and builds, run `sqlite3 awards.sqlite3 "PRAGMA integrity_check;"` → result is exactly `ok`.
5. Compare the pre/post database file hash for the implementation run → hash is unchanged.
6. Handoff explicitly states that current database changes still require a separate data commit before delivery from a clean checkout.

## T1 — Integrate map data and routes into the website builder

**ID:** T1

**Goal:** Make the existing static builder own map aggregation, validation, payloads, and routes.

**Depends-on:** T0

**Files:** `website/build.py:39-68, 89-162, 303-408, 778-835, 1292-1317, 1389-1437`

**Assumptions:** 1, 2, 5, 6

**Steps → verify:**

1. Register `map.html` and `MAP_ROUTE = "/map/"`.
2. Add matching `birth_coordinates` and `affiliation_coordinates` fields to `AWARD_COLUMNS` and `AwardRecord`.
3. Port focused coordinate parsing and aggregation helpers from `map-mvp/build.py`.
4. Preserve one birth point per row and split affiliation coordinates on `;`, counting one point per segment.
5. Group by coordinates, select labels deterministically, preserve blank birth fields, and use “Multiple recorded institutions” for multi-coordinate source rows.
6. Retain total, subject, decade, and subject-by-decade counts in each location.
7. Escape `<` in compact JSON and reject malformed/non-finite/out-of-range coordinates with record ID and field.
8. Plan `/map/` plus one `/map/{subject-slug}/` page per `SUBJECTS` entry; use unique subject-specific titles/descriptions and initial-subject context.
9. Pass `map_route` through normal and error-page template contexts.
10. Build a fixture containing one birth coordinate, two affiliation coordinate segments, two subjects, and two decades → counts and exact combined buckets match.
11. Build fixtures with malformed and out-of-range coordinates → `BuildFailure` names the safe record ID and field.
12. Inspect `create_site_plan()` → map jobs are unique, subject jobs have unique metadata, and `/map/biology/` carries initial subject `Biology`.

## T2 — Copy and adapt the approved map template

**ID:** T2

**Goal:** Convert the standalone MVP into a first-party Jinja page without losing its accepted design or interaction.

**Depends-on:** T1

**Files:** `map-mvp/template.html:1-466` (read-only reference); `website/templates/map.html` (new)

**Assumptions:** 2, 3, 4, 6

**Steps → verify:**

1. Keep `map-mvp/template.html` unchanged and create a separate `website/templates/map.html`.
2. Convert the website copy to extend `base.html`, overriding the body-class, head, and content blocks.
3. Remove duplicated root color/typography variables and inherit the global website palette, typography, links, and dark mode.
4. Put map, shade, card, legend, and fallback inside one positioned `.map-shell` in normal flow with a defined responsive height.
5. Remove viewport-level absolute positioning and `body { overflow: hidden; }`.
6. Preserve the accepted strong teal “Explore the data” label, proportional terracotta/teal circles, filters, toggles, live totals, popups, legend, and “Surprise me.”
7. Use builder-supplied payload and initial subject instead of URL-path parsing.
8. Relabel the combined count “mapped points” and remove “preview” language.
9. Add `<noscript>` fallback; keep a readable runtime fallback if Leaflet fails.
10. After each visible marker is attached, add `tabindex`, a location-and-filtered-count accessible name, and Enter/Space popup activation; refresh semantics after filters.
11. Disable fly animation under `prefers-reduced-motion: reduce`.
12. Preserve DOM text-node popup construction, Leaflet SRI pins, OpenStreetMap attribution, and keyboard-operable form controls.
13. Render `/map/biology/` → Biology is selected, the card and shared shell coexist, marker controls remain interactive, and no source prose is inserted as popup HTML.

## T3 — Add shared navigation and responsive shell support

**ID:** T3

**Goal:** Expose Map as a normal site destination without regressing existing page layouts or mobile navigation.

**Depends-on:** T1

**Files:** `website/templates/base.html:18-50`; `website/static/style.css:56-91`

**Assumptions:** 2, 3, 4

**Steps → verify:**

1. Add a body-class block to `base.html`; leave it empty by default.
2. Add “Map” to shared navigation with `href(map_route)`.
3. Permit `.site-nav` to wrap with a restrained row gap while preserving desktop spacing and alignment.
4. Render a non-map page → body class is empty and its main width/padding are unchanged.
5. Render the map → its body class removes only the map page’s main width/padding constraints.
6. Inspect at 320 CSS pixels → all seven navigation links are visible with no horizontal overflow.
7. Inspect the 404 page → Map points to the configured deployment subpath.

## T4 — Consolidate map verification in the website suite

**ID:** T4

**Goal:** Cover production map behavior independently while retaining the standalone test suite.

**Depends-on:** T1, T2, T3

**Files:** `tests/test_build_website.py:34-78, 101-215, 216-342`

**Assumptions:** 2, 3, 5, 6

**Steps → verify:**

1. Add coordinate parsing tests for longitude/latitude order, boundaries, non-finite values, malformed segments, and semicolon splitting.
2. Add aggregation tests for deterministic labels, alternate labels, blank birth cities, neutral multi-institution labels,
   per-segment counts, subjects, decades, and combined buckets.
3. Assert compact JSON escapes `<`.
4. Assert one `/map/` job and one job per subject, unique titles/descriptions, canonical routes, and correct initial-subject context.
5. Extend complete-build assertions for `/map/index.html`, `/map/biology/index.html`, sitemap entries, shared Map navigation,
   global stylesheet, body class, Leaflet pins, attribution, fallback, “mapped points,” reduced-motion handling, and
   DOM-safe popup code.
6. Add markup assertions for focusable marker semantics and Enter/Space activation.
7. Keep deployment-subpath relative-link validation green for every generated map page.
8. Run `uv run python -m unittest tests.test_build_website` → all tests pass, including the existing metadata, routes, links, sitemap, permissions, and atomic-promotion tests.

## T5 — Retain the standalone implementation

**ID:** T5

**Goal:** Preserve the disposable fallback until the user explicitly approves its removal.

**Depends-on:** T4

**Files:** `map-mvp/build.py:1-253`; `map-mvp/template.html:1-466`; `map-mvp/test_build.py:1-149`; generated `map-mvp/dist/`

**Assumptions:** 1, 7

**Steps → verify:**

1. Keep the tracked standalone builder, template, and tests unchanged.
2. Rebuild `map-mvp/dist/` for local comparison; keep it uncommitted.
3. Run the standalone suite → all tests pass.
4. Confirm production `website/` code does not import or read from `map-mvp/`.

## T6 — Build and inspect the integrated map

**ID:** T6

**Goal:** Prove the accepted MVP works inside the complete generated website.

**Depends-on:** T4, T5

**Files:** `website/dist/` (generated local state; do not commit)

**Assumptions:** 2, 3, 4, 5, 6

**Steps → verify:**

1. Run `uv run website/build.py --base-url https://example.org/awards/` → build succeeds and production output is atomically promoted.
2. Serve `website/dist/` locally and inspect `/map/`, `/map/biology/`, and `/map/math/`.
3. Verify desktop and mobile light/dark layouts → shared header/footer remain reachable, map stays full-width, overlay card is contained, and navigation wraps at 320 pixels.
4. Select Subject and Decade together → markers, radii, popups, and “mapped points” totals use exact combined counts.
5. Toggle both layers independently → circles and totals update without browser errors.
6. Use “Surprise me” with normal and reduced motion → only visible circles are targeted and reduced motion does not animate.
7. Use keyboard only → focus filters, layer buttons, and a marker; Enter/Space opens its popup.
8. Inspect representative normal and multi-coordinate institution popups → normal rows use source labels and ambiguous multi-point rows use the neutral label.
9. Parse `website/dist/sitemap.xml` → `/map/` and every subject-map route use the configured absolute base URL.
10. Run `sqlite3 awards.sqlite3 "PRAGMA integrity_check;"` → result is exactly `ok`.
11. Recheck the T0 database hash → unchanged during integration.
12. Run `git diff --check` and inspect the staged file list → no database, generated output, backup, cache, or unrelated worktree file is included.
13. Commit with a conventional message on `feat/map-mvp`; do not merge until reviewed, then squash-merge into `202607`.
