## Goals

The static awards website MUST include the approved Awards Atlas as a first-party `/map/` page. It MUST preserve the
standalone MVP’s proportional birthplace and institution circles, subject and decade filters, layer toggles, live totals,
popups, responsive layout, clean subject routes, and light/dark visual alignment while adopting the website’s shared header,
navigation, footer, canonical URLs, sitemap, and atomic build.

## Background

The approved MVP is isolated under `map-mvp/`: `build.py` reads `awards.sqlite3`, `template.html` contains the Leaflet page
and interaction, and `test_build.py` verifies aggregation and generation. Commit `baa34dc` preserves that standalone layout.

The production builder registers templates and routes in `website/build.py:39-68`, reads selected award fields through
`AWARD_COLUMNS` and `AwardRecord` at `website/build.py:89-162`, plans all static routes in
`website/build.py:778-1317`, injects shared route context in `website/build.py:1389-1437`, and atomically promotes the
complete generated site. Shared navigation lives in `website/templates/base.html:18-50`. The builder currently omits
`birth_coordinates` and `affiliation_coordinates`, and the website has no map route.

## Assumptions

1. **Load-bearing:** “Merge into the main app” means integrate the MVP into `website/build.py` and generated
   `website/dist/`, not Git-merge `feat/map-mvp` into another branch yet.
2. **Load-bearing:** The canonical routes are `/map/` and `/map/{subject-slug}/`; generic root routes such as `/biology/` are not introduced.
3. The map remains an immersive full-width page in normal flow below the shared site header and above the shared footer.
4. The map is a top-level navigation destination and omits breadcrumbs to preserve the approved overlay layout.
5. Circle area continues to represent award-row count, including one count at each point in a multi-coordinate affiliation row.
6. Leaflet 1.9.4 and OpenStreetMap remain pinned external browser dependencies.
7. The standalone generator, template, tests, and generated preview remain available until the user explicitly approves their removal.

## Builder integration

`website/build.py:39-68, 89-162, 303-408, 778-835, 1292-1317, 1389-1437` SHALL:

- register `map.html` and `MAP_ROUTE = "/map/"`;
- add matching `birth_coordinates` and `affiliation_coordinates` fields to both `AWARD_COLUMNS` and `AwardRecord`;
- port the MVP’s exact coordinate validation and aggregation into ordinary focused helper functions;
- require one valid `longitude,latitude` pair for each nonblank birth coordinate;
- split nonblank affiliation coordinates on semicolons and count one award at every valid pair;
- reject malformed, non-finite, or out-of-range nonblank coordinates with `BuildFailure` naming the record ID and field;
- group birth points by coordinates using `birth_city` and `birth_country`, select deterministic source labels, preserve blank source fields, and report alternate-label counts;
- group affiliation points by coordinates using `affiliation_name`, `affiliation_city`, and `affiliation_country`;
- use the neutral label “Multiple recorded institutions” for every source row with multiple affiliation coordinates rather
  than assigning unsplittable prose to an individual point;
- retain per-location totals for subject, decade, and exact subject-by-decade combinations;
- serialize map payload as compact JSON with `<` escaped;
- add one `/map/` page job with no preselected subject;
- add one `/map/{slug}/` page job for every value in `SUBJECTS`, with that exact subject preselected and a subject-specific title and description;
- pass `map_route` into normal page and error-page template contexts;
- include every map route in duplicate-route validation, canonical URLs, sitemap generation, atomic rendering, and world-readable output through the existing path.

Map helper functions MUST operate only on the already loaded `AwardRecord` objects. The website build MUST remain read-only
with respect to `awards.sqlite3`; no schema or source-data changes are required.

### Requirement: map aggregation — The production builder MUST preserve the verified MVP data contract

#### Scenario: multi-coordinate institution

- WHEN one award row has two semicolon-separated affiliation coordinate pairs
- THEN each coordinate receives one institution award count
- AND the build succeeds against the current database

#### Scenario: invalid coordinate

- WHEN a nonblank coordinate is malformed or outside Earth bounds
- THEN the build fails with the safe record ID and field
- AND the prior `website/dist/` remains intact

### Requirement: map routes — The production plan MUST expose the map and clean subject entries

#### Scenario: direct Biology route

- WHEN `/map/biology/` is generated
- THEN its canonical URL uses the configured deployment base URL
- AND Biology is selected on first render
- AND all other subject, decade, and layer controls remain available

## Template integration

The tracked `map-mvp/template.html:1-466` SHALL remain unchanged. A separate `website/templates/map.html` SHALL adapt its approved design to extend `base.html`. It SHALL:

- inherit the website’s exact global `--paper`, `--surface`, `--ink`, `--muted`, `--accent`, `--rule`, typography, link behavior, and dark-mode values;
- keep only map-specific marker, tile, overlay, control, popup, and responsive CSS in its `head` block;
- contain all map elements inside one positioned `.map-shell` in normal document flow; the shell SHALL have a defined
  responsive height, while map, shade, overlay card, legend, and fallback position relative to that shell rather than the
  viewport;
- remove standalone `body { overflow: hidden; }` and viewport-absolute rules so the shared header and footer remain visible and reachable;
- preserve the accepted full-width map, overlay card, strong “Explore the data” label, proportional terracotta/teal
  circles, filters, layer buttons, legend, and “Surprise me” interaction;
- render compact payload and the planned initial subject from trusted builder context;
- initialize its subject dropdown from payload values and apply the planned initial subject without inspecting or assuming the deployment URL path;
- continue to create popup content through DOM text nodes rather than interpolated HTML;
- make every visible circle marker keyboard-focusable with an accessible location-and-count label and Enter/Space popup activation;
- retain pinned Leaflet integrity metadata, OpenStreetMap attribution, keyboard-operable controls, a `<noscript>` fallback, and mobile behavior;
- label the combined total “mapped points” because one award may contribute both a birth and an affiliation point;
- honor `prefers-reduced-motion: reduce` by moving immediately rather than animating “Surprise me”;
- remove standalone “preview” copy from the first-party page.

`website/templates/base.html:18-50` SHALL:

- provide a template body-class block so the map can opt into a full-width main region without changing other pages;
- add “Map” to shared navigation using `map_route`.

`website/static/style.css:56-91` SHALL allow `.site-nav` to wrap cleanly when the seventh top-level link is added. The
map-specific body class SHALL affect only the map page. No prize route, explorer behavior, or existing content output may
change.

### Requirement: shared-site presentation — The map MUST look and navigate like a first-party website page

#### Scenario: normal website build

- WHEN `/map/` is rendered
- THEN it includes the shared site header, Map navigation link, footer, favicon, global stylesheet, canonical metadata, and map content
- AND its map region remains full-width and responsive

#### Scenario: keyboard marker access

- WHEN a keyboard user focuses a visible marker and presses Enter or Space
- THEN its accessible name identifies the location and filtered point count
- AND its popup opens

#### Scenario: small-screen navigation

- WHEN the site is viewed at 320 CSS pixels
- THEN all seven top-level navigation links remain visible without horizontal overflow

#### Scenario: deployment subpath

- WHEN the site builds with `--base-url https://example.org/awards/`
- THEN map canonical and navigation links use `/awards/` correctly
- AND no internal link resolves outside generated output

## Standalone retention

`map-mvp/build.py:1-253`, `map-mvp/template.html:1-466`, and `map-mvp/test_build.py:1-149` SHALL remain intact as the
disposable fallback. Its generated `map-mvp/dist/` preview MAY remain as uncommitted local state for comparison. The
production website MUST NOT import or depend on any standalone file; its independent path is
`website/build.py` → `website/templates/map.html` → `website/dist/map/`.

## Verification

`tests/test_build_website.py:34-78, 101-215, 216-342` SHALL cover:

- coordinate order, semicolon splitting, finite/bounds validation, and safe failures;
- deterministic location labels and counts;
- blank birthplace-city display behavior;
- exact subject, decade, and subject-by-decade counts;
- compact JSON escaping;
- `/map/` and every `/map/{subject}/` plan job;
- initial-subject context;
- shared navigation, body class, Leaflet pins, OpenStreetMap attribution, fallback markup, and DOM-safe popup construction;
- deployment-subpath-safe canonical and relative links;
- map and subject-map sitemap entries;
- successful real-template generation independent of the retained standalone map files;
- keyboard marker semantics, `<noscript>` fallback, reduced-motion handling, “mapped points” copy, and 320-pixel navigation wrapping.

Run:

`uv run python -m unittest tests.test_build_website`

Then run:

`uv run website/build.py --base-url https://example.org/awards/`

Inspect `/map/`, `/map/biology/`, and `/map/math/` in desktop and mobile light/dark modes. Verify subject and decade filters
combine, layer toggles change circles and totals, “Surprise me” targets visible circles, and representative popups are
accurate. Finally verify:

`sqlite3 awards.sqlite3 "PRAGMA integrity_check;"`

returns exactly `ok`.

Before the integration branch is delivered from a clean checkout, the existing tracked `awards.sqlite3` coordinate
corrections—including verified UC Berkeley and UCSF affiliation coordinates—MUST be preserved in a separate data commit.
The map integration commit MUST NOT absorb unrelated current database changes.

## Scope

Expected implementation: five application/test paths and approximately 320–480 net lines:

- `website/build.py:39-68, 89-162, 303-408, 778-835, 1292-1317, 1389-1437`
- `website/templates/map.html` (new first-party adaptation of `map-mvp/template.html:1-466`)
- `website/templates/base.html:18-50`
- `website/static/style.css:56-91`
- `tests/test_build_website.py:34-78, 101-215, 216-342`

Implementation stays on `feat/map-mvp`, uses conventional commits, generates unit tests alongside integration, and MUST be
reviewed before squash-merging into the `202607` month branch.
