## Goals

Add the already-calculated PPP ranking to the homepage and make PPP the initial Explorer GDP-per-capita selection. The homepage MUST present the complete top 15 as a normal PrizeAtlas ranking list, with links to the existing award-affiliation country pages. Both surfaces MUST state plainly that the denominator is 2024 World Bank GDP-per-capita data at purchasing-power parity (PPP), in current international dollars.

Success is verifiable when `/explorer/` initially renders the PPP series, its selector visibly starts on PPP, and `/` renders the same up-to-15 PPP countries, in the same rank order and with the same displayed rate, using the homepage's existing `highlights` list treatment.

## Background

The Explorer already embeds server-ranked `gdp_per_capita_rankings` for `nominal` and `ppp` in `website/build.py:498-526,529-641`; the ranking counts each award row once per distinct recorded affiliation country and uses `award rows / GDP per capita × 1,000`. `website/templates/explorer.html:168-180,510-557` presently makes nominal GDP per capita the selected and initially drawn measure, even though both 2024 World Bank series are available.

The homepage is a static Jinja page. `website/build.py:2260-2333` currently assembles its ranking contexts, and `website/templates/index.html:78-104` renders its country rankings as linked ordered `highlights` lists. `create_site_plan` creates the Explorer payload before it plans the homepage at `website/build.py:2505-2523`, so the homepage can reuse the computed PPP result list without adding another data source, browser request, or calculation.

The existing top-15 Explorer list is a ranking of recorded award affiliations, while the existing homepage country lists are ranked by merged people. The new text therefore needs to identify awards and award-time affiliation explicitly, rather than calling the rows laureates.

## Assumptions

1. **Load-bearing:** The requested “same style as the other rankings” means the homepage uses the existing static `highlights` ordered-list treatment, not a second JavaScript/SVG chart.
2. **Load-bearing:** “This diagram” retains the previously requested top-15 limit on the homepage; it does not inherit the unrelated `HOMEPAGE_ROWS = 8` limit used by other homepage sections.
3. **Load-bearing:** The homepage's country links target the already-generated `/countries/awarded/{country}/` pages because both surfaces are attributed to recorded affiliation countries at the time of the award.
4. The new display reuses the existing 2024 PPP results and does not alter `website/population.json`, SQLite data, award counts, threshold, or ranking formula.
5. The repository's local policy currently disallows branches; implementation will follow that policy instead of the generic branch/squash guidance.

## Explorer default

Update `website/templates/explorer.html:168-180,510-557` so that the `GDP per capita, PPP (current international $)` option is selected in the document and the first `draw` call uses `ppp`. The nominal option SHALL remain available, and a change event SHALL continue to replace only the GDP chart with its pre-ranked nominal or PPP rows.

The chart's explanatory paragraph SHALL state that it shows recorded awards per $1,000 of 2024 World Bank GDP-per-capita data, uses recipients' affiliation country at the time of award, and requires five awards. It SHALL name PPP as the initial measure and identify its current-international-dollar unit. This wording MUST not call the award counts laureates, imply total GDP or GDP per person beyond the established GDP-per-capita indicator name, or claim inflation-adjusted real GDP.

### Requirement: PPP is the initial Explorer measure — MUST

#### Scenario: Load the Explorer

- WHEN a reader opens `/explorer/` without interacting with the selector
- THEN the control displays `GDP per capita, PPP (current international $)`
- AND the chart draws the existing PPP ranking rows, up to 15 countries.

#### Scenario: Switch to nominal

- WHEN a reader selects `GDP per capita (current US$)`
- THEN the chart replaces its bars with the existing nominal ranking rows
- AND the text, threshold, rate unit, and accessible SVG labels remain accurate for the selected metric.

## Homepage PPP ranking

Update `website/build.py:2260-2333,2505-2523` to pass a small presentation-ready sequence for the existing PPP ranking to `index.html`. Resolve each Explorer country index through the Explorer country-name list and the `country_places["Awarded"]` route map. Each retained row SHALL contain only the country name, award-affiliation country route, award-row count, and precomputed rate.

The build SHALL keep the Explorer's ordering and rate unchanged, retain all eligible entries up to the existing 15-row GDP ranking limit, and omit an entry only when the country lacks a generated award-affiliation country page. A missing country route SHALL not trigger a derived route or a second ranking calculation. This makes route availability explicit and preserves the generated site's existing route contract.

Update `website/templates/index.html:78-104` to add one static section beside the existing country rankings using `<ol class="highlights">`. It SHALL be headed `Awards per 2024 GDP per capita (PPP)` and include a concise visible description substantially equivalent to: “Recorded awards by affiliation country at the time of award, per $1,000 of 2024 World Bank GDP per capita, PPP (current international $).” Each list item SHALL link the country name and show the precomputed rate rounded to exactly two decimal places with `awards / $1,000`; it MAY also show the award-row count if that remains concise.

The new section MUST use no client-side script, selector, duplicated snapshot lookup, new page route, or total-GDP/per-person calculation. If the PPP list has no routeable entries, the section SHALL be omitted in the same conditional style as the adjacent homepage rankings.

### Requirement: Homepage PPP ranking is rigorous and matches Explorer — MUST

#### Scenario: Build the homepage with eligible PPP rows

- WHEN the static site plan has PPP GDP-per-capita ranking rows and matching awarded-country routes
- THEN the homepage renders them in Explorer PPP order, limited to the existing top 15
- AND every visible section description identifies 2024 World Bank GDP per capita, PPP, current international dollars, awards, affiliation country at award time, and the per-$1,000 unit.

#### Scenario: A ranked country has no homepage route

- WHEN an Explorer PPP row names a country for which no `/countries/awarded/` page was planned
- THEN that homepage entry is left out without inventing a route
- AND the remaining rows retain their Explorer ordering and values.

#### Scenario: No routeable PPP rows

- WHEN no PPP-ranking country has a generated award-affiliation route
- THEN the homepage omits the new section
- AND the existing homepage sections continue to render unchanged.

## Tests and verification

Update `tests/test_build_website.py:156-423` and the focused homepage-plan assertions near `tests/test_build_website.py:375-394`.

Tests SHALL assert the changed Explorer template contract: PPP is the selected option, PPP is the initial draw argument, nominal remains selectable, and the visible note contains the exact 2024/World Bank/affiliation/award semantics. They SHALL also construct more than 15 presentation-ready PPP rows with a missing route, verify that the homepage context holds only routeable rows in the original order without recalculating rates, and assert the homepage template's 2024 PPP heading, precise explanatory text, `highlights` class, country link, and exactly two-decimal `awards / $1,000` unit.

Implementation verification SHALL run the focused website unit tests, `uv run ruff check website/build.py tests/test_build_website.py`, and `uv run website/build.py --base-url http://localhost:8000/`. The rebuilt `website/dist/index.html` and `website/dist/explorer/index.html` SHALL be inspected for the visible 2024 PPP wording, two-decimal rate format, and correct PPP ordering. `--home-only` is insufficient because it cannot render the changed Explorer template; generated `website/dist/` remains unversioned.

Estimated scope: 4 files changed (`website/build.py`, `website/templates/explorer.html`, `website/templates/index.html`, and `tests/test_build_website.py`), approximately 45–65 implementation and test lines. No database, schema, data snapshot, or public route changes are expected.

## Implementation constraints

Generate or update unit tests alongside the implementation. Keep the supplied ranking formula and 2024 World Bank snapshot immutable. Do not modify unrelated dirty worktree changes. Use conventional commits only if a commit is requested; do not create a branch because the repository's explicit local policy says not to use branches, and do not merge until reviewed.
