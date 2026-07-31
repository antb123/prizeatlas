# Homepage PPP GDP Ranking — Implementation TODO

Execution constraint: the repository does not use branches. Preserve existing dirty worktree changes; do not write or change the 2024 snapshot, database, schema, or routes. Generate tests with the implementation and use conventional commits only if a commit is requested.

## T1 — Reuse Explorer PPP rankings in the homepage plan

- ID: `T1`
- Depends-on: none
- Files: `website/build.py:2260-2333,2505-2523`
- Goal: Pass a routeable, presentation-ready PPP country ranking from the existing Explorer payload to the homepage without a second calculation.
- Assumptions:
  1. **Load-bearing:** The homepage needs the full existing top 15 rather than the normal `HOMEPAGE_ROWS = 8` slice.
  2. **Load-bearing:** Country links target generated `/countries/awarded/{country}/` routes because the values are award-time affiliation-country counts.
  3. The existing 2024 PPP data and ranking formula are immutable.
- Steps → verify:
  1. After `explorer_payload` is built, resolve its `ppp` rows through the payload country-name list and a name-to-`Place` map from `country_places["Awarded"]`.
  2. Pass only the country name, generated awarded-country route, award-row count, and existing rate to `plan_home_page`/`index.html`; retain payload order and values exactly.
  3. Skip a row with no corresponding generated route; do not construct a route from a slug or recompute the rate. Omit the new context when no rows survive.
  4. Confirm a synthetic context with more than 15 ranked rows retains the existing list cap, routeable order, and unmodified numeric rates.

## T2 — Make PPP the Explorer default and state the 2024 basis

- ID: `T2`
- Depends-on: none
- Files: `website/templates/explorer.html:168-180,510-557`
- Goal: Make PPP the initially selected chart series while preserving the nominal selection and give readers a rigorous visible description.
- Assumptions:
  1. **Load-bearing:** The existing `gdp_per_capita_rankings.ppp` list is authoritative; no browser-side ranking calculation is added.
  2. **Load-bearing:** Awards count distinct populated affiliation countries per award row, not distinct laureates, births, total GDP, or a real-GDP series.
  3. The selected metric remains 2024 World Bank GDP per capita at PPP in current international dollars.
- Steps → verify:
  1. Make `GDP per capita, PPP (current international $)` the selected `<option>` and call `draw("ppp")` on initial load; retain nominal as a selectable option and retain the current change handler.
  2. Rewrite the visible explanatory note to identify the top 15, recorded awards, affiliation country at award time, the five-award threshold, 2024 World Bank GDP per capita, PPP, and current international dollars.
  3. Keep the status message, per-bar tooltip, SVG title, and SVG description accurate for either selector choice.
  4. Confirm the no-eligible-row message still appears and that switching to nominal consumes only `GDP_PER_CAPITA_RANKINGS.nominal`.

## T3 — Render the static PPP ranking on the homepage

- ID: `T3`
- Depends-on: `T1`
- Files: `website/templates/index.html:78-104`
- Goal: Add the full routeable PPP top-15 as a standard homepage ranking list.
- Assumptions:
  1. **Load-bearing:** “Same style as other rankings” is the existing static `<ol class="highlights">` design, not an SVG or interactive duplication of the Explorer chart.
  2. **Load-bearing:** The visible text must name 2024 World Bank GDP per capita, PPP, current international dollars, awards, and affiliation country at award time.
  3. Homepage rates use the Explorer-provided value formatted to exactly two decimal places.
- Steps → verify:
  1. Add a conditional section beside the existing country ranking sections headed `Awards per 2024 GDP per capita (PPP)`.
  2. Include a concise description equivalent to “Recorded awards by affiliation country at the time of award, per $1,000 of 2024 World Bank GDP per capita, PPP (current international $).”
  3. Render each routeable PPP entry in order with a country link and `N.NN awards / $1,000`; include award-row count only if it remains concise.
  4. Confirm a page with no rows omits the whole section and has no empty heading/list.

## T4 — Add focused regression coverage and build verification

- ID: `T4`
- Depends-on: `T1`, `T2`, `T3`
- Files: `tests/test_build_website.py:156-423`
- Goal: Lock the default, rigorous labels, data reuse, ordering, and rendered rate format.
- Assumptions:
  1. **Load-bearing:** PPP default is observable in both the selected markup option and the initial `draw` argument.
  2. **Load-bearing:** Homepage output is drawn from the existing Explorer PPP ranking, preserving its order/value and top-15 cap without recalculation.
  3. A full site build, not `--home-only`, is required after this change because `/explorer/` is changed.
- Steps → verify:
  1. Extend the Explorer template contract assertion for selected PPP, initial PPP draw, selectable nominal, and the 2024/World Bank/PPP/affiliation/award wording.
  2. Add a home-plan fixture with more than 15 PPP inputs and one country without a route. Assert only routeable rows are passed, their order/rates are unchanged, and their displayed rate is two decimal places.
  3. Assert the homepage template contract for its heading, precise 2024 PPP explanation, `highlights` ordered list, country link, and `awards / $1,000` label.
  4. Run:
     - `uv run python -m unittest tests.test_build_website.WebsiteBuildTests.test_explorer_section_order_and_chart_limits` plus the new homepage GDP test;
     - `uv run ruff check website/build.py tests/test_build_website.py`;
     - `uv run website/build.py --base-url http://localhost:8000/`.
  5. Inspect the rebuilt `/explorer/` and `/` pages. Verify PPP is initially selected in Explorer and both pages visibly identify the 2024 World Bank GDP-per-capita PPP basis, award-time affiliation attribution, and two-decimal rate.
