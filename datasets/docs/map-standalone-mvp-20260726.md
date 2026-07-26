## Goals

Create a small standalone map MVP, completely outside `website/`, for reviewing the visual layout before any site integration. The MVP MUST display laureate birthplaces and affiliated institutions as separate world-map layers. Each location MUST use a proportional circle whose area increases with the number of recorded awards at that location.

## Background

`awards.sqlite3` is the sole data source. The `awards` table contains `birth_coordinates` and `affiliation_coordinates` in `longitude,latitude` order, with 3,047 award rows carrying birth coordinates and 1,452 carrying affiliation coordinates. The repository has no standalone map prototype today. The production static site is generated under `website/`, but this MVP is explicitly isolated from that code until its layout is accepted.

The smallest useful prototype is one generated HTML page using Leaflet and OpenStreetMap tiles. A short build script reads the database, aggregates locations, and writes the map with inline JSON. No uMap account or manual upload is needed.

## Assumptions

1. **Load-bearing:** The MVP lives entirely under a new top-level `map-mvp/` directory and changes nothing under `website/`.
2. **Load-bearing:** Circle size represents award-row count, not distinct laureates or weighted prestige.
3. Birthplaces and institutions are independently toggleable layers and are both visible initially.
4. Points are grouped by coordinates alone so overlapping labels at one point become one inspectable circle.
5. Leaflet 1.9.4 loads from pinned CDN URLs; OpenStreetMap supplies map tiles.
6. This MVP has subject and decade filtering but no search, clustering, geolocation, analytics, or production-site navigation.
7. A semicolon-separated affiliation coordinate string contributes one award count to every listed coordinate.

## Standalone generator

New `map-mvp/build.py` SHALL:

- open `awards.sqlite3` through a SQLite URI with `mode=ro` and enable `PRAGMA query_only=ON`;
- select only the fields needed for birthplace and institution markers;
- require each nonblank birth coordinate string to contain exactly one `longitude,latitude` pair;
- split nonblank affiliation coordinate strings on semicolons and parse every segment as one `longitude,latitude` pair;
- reject malformed, non-finite, or out-of-range coordinates with an error naming the exact `award_record_id` and field;
- aggregate birthplace rows by coordinates, using `birth_city` and `birth_country` as its source label fields;
- aggregate institution rows by coordinates, using `affiliation_name`, `affiliation_city`, and `affiliation_country` as its source label fields;
- count award rows in each group;
- retain exact high-school-subject, decade, and subject-by-decade counts for combined filtering;
- choose each circle's primary label by highest row count, breaking ties alphabetically, and retain the number of additional labels represented at that coordinate;
- sort output deterministically;
- serialize the two marker arrays as compact inline JSON with `<` escaped;
- render `map-mvp/template.html` to `map-mvp/dist/index.html`;
- emit one equivalent subject route such as `map-mvp/dist/biology/index.html` for every recorded high-school subject;
- create output through a staging file and replace the prior output only after successful rendering.

The script MUST NOT modify `awards.sqlite3`, `website/`, or any source dataset.

For a multi-coordinate affiliation row, every emitted coordinate retains the row's complete affiliation name, city, and country strings; the generator MUST NOT guess which semicolon-delimited prose belongs to which coordinate. A birth label with a blank city retains that blank source value. Its popup uses `birth_country` as the visible heading when available, otherwise the neutral interface text “Unnamed birthplace”; this fallback MUST NOT be written into source data or serialized as a source label.

### Requirement: proportional circles — Circle area MUST represent award count

#### Scenario: repeated location

- WHEN five award rows share the same coordinates
- THEN the map emits one circle with count five
- AND its visible area is larger than a one-award circle

#### Scenario: invalid coordinate

- WHEN a nonblank coordinate is malformed or outside Earth bounds
- THEN generation fails with the record ID and field
- AND the previous generated map remains intact

#### Scenario: multi-coordinate affiliation

- WHEN one award row contains two semicolon-separated affiliation coordinate pairs
- THEN it contributes one award to the circle at each coordinate
- AND both points retain the complete source affiliation name, city, and country strings

#### Scenario: blank birthplace city

- WHEN a coordinate-bearing birth row has a blank `birth_city`
- THEN the source city remains blank
- AND the popup uses the source `birth_country` as its heading, or “Unnamed birthplace” when both fields are blank

## Standalone page

New `map-mvp/template.html` SHALL produce one generated page containing:

- a title and short explanation that the MVP visualizes current dataset coordinates and may expose unresolved coordinate errors;
- a full-width world map;
- visible Birthplaces and Institutions layer toggles;
- High-school subject and award-decade dropdowns that combine exactly and update circles, popups, and totals;
- automatic subject selection on clean subject routes such as `/biology/`, `/math/`, and `/earth-science/`;
- a small legend showing each layer color and explaining circle area;
- proportional Leaflet circle markers with radius `2.5 × sqrt(award count)` CSS pixels, so circle area tracks count exactly;
- birthplace popups containing the primary `birth_city`, `birth_country`, award count, and number of additional recorded labels at that coordinate;
- institution popups containing the primary `affiliation_name`, `affiliation_city`, `affiliation_country`, award count, and number of additional recorded labels at that coordinate;
- an initial world view with both layers enabled;
- responsive layout usable at 320 CSS pixels;
- a readable unavailable message if Leaflet cannot initialize.

All CSS and MVP JavaScript SHALL remain in `map-mvp/template.html`. Database text MUST enter popups through DOM text nodes, not HTML interpolation. Leaflet and map tiles remain external network dependencies.

### Requirement: independent layers — Reviewers MUST be able to compare birthplace and institution distributions

#### Scenario: toggle one layer

- WHEN Birthplaces is disabled
- THEN all birthplace circles disappear
- AND institution circles remain visible

### Requirement: student filters — Reviewers MUST be able to focus the map by subject and decade

#### Scenario: combined filters

- WHEN Math and the 1990s are selected
- THEN only Math-classified award points from the 1990s remain
- AND circle sizes, popups, and totals use the combined count

#### Scenario: subject route

- WHEN `/biology/` opens
- THEN Biology is selected automatically
- AND the decade and layer controls remain available

## Verification

New `map-mvp/test_build.py` SHALL cover:

- coordinate order and boundary validation;
- semicolon-separated affiliation coordinates and one-count-per-coordinate behavior;
- blank birthplace city display behavior without source-value invention;
- deterministic grouping and award counts;
- exact subject, decade, and combined subject-by-decade counts;
- clean subject-route generation;
- square-root radius behavior;
- safe JSON serialization;
- successful generation of `map-mvp/dist/index.html`;
- expected Leaflet pin, OpenStreetMap attribution, controls, legend, and fallback markup.

Run:

`uv run python map-mvp/test_build.py`

Then generate the real MVP:

`uv run map-mvp/build.py`

Open `map-mvp/dist/index.html` locally, confirm both layers render, circles visibly scale with award counts, toggles work, and representative popups show the correct location and count. Finally verify:

`sqlite3 awards.sqlite3 "PRAGMA integrity_check;"`

returns exactly `ok`.

## Scope

Expected implementation: three new source files and approximately 400–550 lines, all removable together by deleting `map-mvp/`:

- `map-mvp/build.py` (new)
- `map-mvp/template.html` (new)
- `map-mvp/test_build.py` (new)

`map-mvp/dist/index.html` is disposable generated output. No existing application, test, configuration, schema, generated website, or database file SHALL change. Deleting `map-mvp/` MUST remove the implementation, its test, and its generated output without leaving references elsewhere. Implementation SHALL use one branch for this specification, conventional commits, tests alongside implementation, and review before any later merge into `website/`.
