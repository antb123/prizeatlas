## Goals

Map popups MUST let a visitor continue from a plotted location to the existing page for an institution or laureate. An institution popup must make the institution title a link, distinguish its institution-wide laureate total from the winners represented at the plotted point under the active filters, and list those represented winners as links. A birthplace popup must list its represented winners as links. Existing marker filtering, award-point totals, keyboard operation, and deployment-subpath support must continue to work.

## Background

`website/build.py:518-590` currently aggregates map rows by coordinates into counters and retains only a primary place label plus award counts. It discards laureate identity, person routes, and institution routes before serializing the payload. `website/templates/map.html:291-319` therefore builds a DOM-safe popup containing plain text only: a place or institution title, location, recorded-award count, and optional notice about other labels at that coordinate.

The site already plans stable laureate routes in `website/build.py:1046-1068`, award-detail routes in `website/build.py:1240-1461`, and institution detail routes in `website/build.py:893-958` and `website/build.py:1752-1773`. Links rendered by a map page must use the same relative-route behavior as other static pages because the configured base URL may include a deployment subpath and subject maps are nested beneath `/map/`.

The live database confirms why the two institution counts must be distinguished: Harvard University currently has 90 award rows at `-71.1169,42.3744` and another 27 at `-71.1039,42.3369`. A marker-local count cannot be presented as Harvard's institution-wide count. Large popup membership is also real rather than hypothetical: current points include dozens of distinct winners, so an unbounded list would exceed a mobile viewport.

The focused map assertions are in `tests/test_build_website.py:273-355` and the generated-page assertions are in `tests/test_build_website.py:462-477`. `website/build.py` and `tests/test_build_website.py` already contain unrelated uncommitted user changes; implementation must preserve them.

## Assumptions

1. **Load-bearing:** “Same for people” means each winner name represented in a birthplace or institution popup is visible and clickable.
2. **Load-bearing:** A stable `/people/{name}/` route is preferred; when a row has no laureate Wikidata QID and therefore no person page, its winner name links to that row's existing award-detail page.
3. A marker's size, the global “mapped points” total, and the existing recorded-award line remain award-record counts; winner counts are additional distinct-recipient counts.
4. Subject and decade filters apply to the marker-local winner count and winner list; the institution-wide laureate total remains the same value shown on the institution detail page.
5. When multiple institution routes share one coordinate, the popup shows each represented institution separately instead of linking only the current primary label.
6. Laureates are deduplicated by their resolved destination route within one popup institution or birthplace.
7. Existing project guidance forbids branches, so implementation remains in the current checkout and does not create the branch otherwise suggested by the generic specification workflow.
8. A recorded affiliation with no corresponding institution detail route remains visible as an unlinked heading; recipient links still work.

## Change surface

| File | Current lines | Change | Estimated implementation |
|---|---:|---|---:|
| `website/build.py` | 518-590, 893-958, 1849-1871 | Preserve popup members and their routes in the map payload; pass existing person, award, and canonical institution metadata into map aggregation. | 50-75 LOC |
| `website/templates/map.html` | 192-204, 291-319, 369-389 | Render linked institution headings, distinct counts, and bounded linked winner lists using DOM APIs and deployment-safe relative URLs. | 65-95 LOC |
| `tests/test_build_website.py` | 273-355, 462-477 | Verify payload identities, distinct counts, fallback award links, multiple institutions at one coordinate, filter metadata, escaping, and generated relative links. | 35-55 LOC |

Expected scope: 3 files and approximately 150-225 changed or added implementation/test lines. No database, schema, generated output, static stylesheet, or route changes are required.

## Payload

### Requirement: Popup membership — the payload MUST retain linkable recipients

`map_payload` MUST receive the already-planned laureate and award-detail route mappings plus institution metadata from `plan_affiliations` rather than independently inventing identities or totals. Each coordinate marker MUST retain the minimum member data needed to:

- identify the displayed winner;
- select the existing person route or award-detail fallback route;
- identify the record's subject and decade for client-side filtering; and
- for affiliation points, group the member under the canonical planned institution name and route and expose the same institution-wide laureate total used by its detail page.

Institution groups MUST be keyed by their planned destination route, not raw recorded spelling, so aliases that fold to one existing detail page produce one popup section. A mapped affiliation without a planned destination route MUST retain its recorded display fallback as an unlinked group.

The existing aggregate `count`, `subjects`, `decades`, and `subject_decades` fields MUST remain available so marker radii, visibility, totals, and current filter behavior are unchanged.

#### Scenario: Recipient with a person page

- WHEN a mapped award row has a nonblank laureate Wikidata QID
- THEN its popup member route is the existing `/people/{name}/` route
- AND repeated awards for that route can be deduplicated into one displayed winner

#### Scenario: Recipient without a person page

- WHEN a mapped award row has no laureate Wikidata QID
- THEN its popup member route is that row's existing award-detail route
- AND no new person route is created or inferred

#### Scenario: Institutions share coordinates

- WHEN awards for two institution names use the same coordinate
- THEN the marker retains both institution names, their existing detail routes, and their respective members
- AND neither institution link is mislabeled as representing the other

#### Scenario: Recorded aliases share one institution route

- WHEN two recorded institution spellings resolve to the same planned detail route
- THEN the popup contains one institution group using the planned canonical display name
- AND its members are combined and deduplicated

## Popup behavior

### Requirement: Institution navigation — institution headings MUST be links

For every represented institution remaining after the active filters, the popup MUST render:

- its name as an anchor to the existing institution detail page;
- its institution-wide laureate total from the planned institution page;
- its number of distinct winners represented at this mapped point under the active filters; and
- those winners as linked names.

The copy MUST make the scopes explicit, for example “22 winners shown at this mapped location · 101 laureates institution-wide.” The popup MAY retain a compact notice when more than one institution is represented, but MUST NOT hide the secondary institutions behind an unlinked count. An institution with no detail route MUST use the same structure with a plain-text heading and without an institution-wide total.

#### Scenario: Harvard marker

- WHEN a visitor opens a marker that represents Harvard University
- THEN “Harvard University” links to its `/affiliations/harvard-university/` page
- AND the popup distinguishes Harvard's institution-wide laureate total from the filtered winners at that mapped point
- AND its represented winner names link to their person or award-detail pages

### Requirement: Birthplace navigation — birthplace popups MUST link their winners

A birthplace popup MUST keep the place heading and location text, then show the distinct represented winner count and linked winner names for the active filters. The city heading itself remains plain text because this request does not introduce a city-detail destination.

Winner names MUST use a semantic list in deterministic alphabetical order. Institution groups MUST be ordered by descending filtered winner count and then canonical name. The winner-list region MUST have a viewport-bounded maximum height and `overflow: auto` so large points remain usable on mobile and by keyboard without adding pagination.

#### Scenario: Several winners share a birthplace

- WHEN multiple laureates at one coordinate pass the active filters
- THEN each distinct laureate appears once in the popup
- AND each name links to the existing person page or award-detail fallback

### Requirement: Filter consistency — popup membership MUST follow visible marker filters

The popup MUST derive its institution groups, distinct winner counts, and winner lists from the same selected subject and decade used for `visibleCount`. Changing a filter and reopening an existing marker MUST not show recipients excluded by that filter.

#### Scenario: Combined filters

- WHEN both a subject and decade are selected
- THEN only members matching both values appear and contribute to winner counts
- AND the marker's existing recorded-award count continues to match its filtered radius and global total

## Links, safety, and accessibility

The payload MUST contain route paths, not prebuilt HTML. `website/templates/map.html` MUST continue constructing popup content with `document.createElement`, `textContent`, and element attributes; dataset strings MUST NOT be interpolated into `innerHTML`.

The template MUST resolve logical routes through the current map page's generated deployment-relative root so links work on `/map/`, `/map/{subject}/`, and a `--base-url` containing a subpath. It MUST NOT hard-code a domain, localhost URL, or root-relative deployment path.

Institution and winner anchors MUST be keyboard focusable by their native semantics. Existing focusable marker behavior and Enter/Space popup activation in `website/templates/map.html:321-338` MUST remain unchanged.

## Verification

Focused tests MUST prove:

1. `map_payload` retains a person route for a QID-backed laureate and an award-detail fallback route for a row without a QID.
2. Two awards held by one routed laureate produce two mapped award points but one distinct displayed winner.
3. Harvard-style multi-coordinate data exposes one institution-wide total while each marker retains only its own filtered members.
4. Two genuinely distinct institution routes sharing coordinates remain separately named and routed, while spelling aliases with one route collapse to the planned canonical institution.
5. Subject and decade metadata are sufficient to exclude nonmatching popup members.
6. Institution groups and winner names have deterministic ordering.
7. A generated `/map/` page and `/map/biology/` page contain deployment-safe link resolution for institution and winner destinations.
8. Hostile names containing HTML-like text remain data/text and cannot become popup markup.
9. Existing map payload, map planning, accessibility, Leaflet integrity, and complete-build assertions still pass.

Implementation verification SHALL run:

`uv run python -m unittest tests.test_build_website.WebsiteBuildTests`

Manual acceptance SHALL build with a deployment subpath, serve `website/dist/`, and check `/map/` and `/map/biology/`: open Harvard at each plotted coordinate, follow its title, follow a winner name, apply combined subject/decade filters, and keyboard-scroll a large winner list. This covers runtime DOM behavior that source-string unit assertions do not execute.

No generated `website/dist/` output is committed.

## Compatibility and exclusions

This change adds fields to the embedded `map-data` JSON but does not remove or rename existing fields. There is no database migration, database write, route migration, analytics event, network request, or server-side behavior. Institution-wide totals on detail pages remain authoritative; popup “shown” counts are scoped to the plotted coordinate and active filters. Changing marker sizing from awards to distinct winners, adding city pages, clustering, pagination, or redesigning the map is out of scope.

Implementation should use a conventional commit if the user later requests a commit. It must preserve unrelated working-tree changes and must not commit generated output.
