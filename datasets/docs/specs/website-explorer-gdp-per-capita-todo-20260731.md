## Execution constraint

The repository instruction currently says not to use branches, so this TODO must run on the current branch and does not
create, merge, or squash a branch. If the user later requests a commit, use a conventional commit; do not push without
an explicit request. Generated `website/dist/` remains untracked local output.

## T1 — Snapshot exact 2024 GDP-per-capita data

**ID:** T1

**Depends-on:** none

**Files:** `website/population.json:1-111`

**Relevant assumptions:**

2. **Load-bearing:** The denominator is 2024 GDP per capita only: nominal current US dollars or PPP current international dollars, selected by the reader.
6. The static World Bank snapshot is refreshed manually; the build and browser MUST NOT fetch economic data.

**Steps → verify:**

1. Preserve `source` and `population` exactly. Add `gdp_per_capita_source` with the World Bank indicator code,
   exact 2024 period, and retrieval date for `NY.GDP.PCAP.CD` and `NY.GDP.PCAP.PP.CD`.
2. Add `gdp_per_capita.nominal` and `.ppp` maps containing only source observations dated exactly 2024, with values
   keyed to dataset country names. Apply only the reviewed aliases in
   `website-explorer-gdp-per-capita-20260731.md:56-71`; do not retain World Bank aggregate countries or aliases as
   duplicate keys.
3. Omit a metric with no exact 2024 observation; specifically leave `Cuba`, `Venezuela`, and `Yemen` absent until
   both the source and a future specification say otherwise. Do not substitute an older observation.
4. Verify with `jq` that both maps are objects, every value is positive JSON number, representative keys are
   `Czech Republic`, `South Korea`, and `Turkey` rather than their World Bank aliases, and the source metadata names
   the two specified indicators.

**Acceptance scenarios covered:** “complete 2024 values” and “unrepresented country.”

## T2 — Build pre-ranked award-to-GDP-per-capita results

**ID:** T2

**Depends-on:** T1

**Files:** `website/build.py:489-582`

**Relevant assumptions:**

1. **Load-bearing:** “Awards” means one `AwardRecord` per distinct populated affiliation country, so repeat winners contribute one count for each award row and a multi-country award contributes once to each country.
3. **Load-bearing:** The displayed rate is `award rows / GDP per capita × 1,000`, labelled “awards per $1,000 GDP per capita”; it is not a total-GDP, population, or distinct-laureate rate.
4. The chart displays the top 15 eligible countries, breaking equal rates by exact dataset country name in ascending order.
5. A country is eligible only with a positive, exact-2024 denominator and at least five recorded award rows, using the same numeric threshold as the existing Explorer rate charts.

**Steps → verify:**

1. Add a small snapshot loader for one GDP-per-capita map and a pure ranking helper that takes country names,
   affiliation-country award-row counts, and one source map. The helper returns at most 15 entries with country index,
   award count, denominator, and unrounded rate.
2. In `explorer_payload`, tally every distinct nonblank affiliation country per award row, independent of QID/person
   merging. Count duplicate units in the same country once and multi-country awards once in each country. Append source
   countries missing from the established `countries` array only after existing country construction, ordered by exact
   dataset country name, so all current indices and payload values retain their existing position.
3. Call the helper once for nominal and once for PPP, adding
   `gdp_per_capita_rankings = {nominal: [...], ppp: [...]}` to the existing payload. Exclude a count below five or a
   missing, zero, or negative denominator; sort by descending unrounded rate then exact dataset country name.
4. Preserve the population loader, `plan_per_capita_places`, existing `people` data, and `explorer_json` escape
   unchanged.
5. Verify the helper has no database, file-system, browser, or network dependency and `explorer_payload` still makes
   one pass over the records and no new database query.

**Acceptance scenarios covered:** “unrepresented country,” “minimum and invalid values,” and the data side of
“initial display” and “PPP selection.”

## T3 — Render the dropdown chart and accessible state

**ID:** T3

**Depends-on:** T2

**Files:** `website/templates/explorer.html:150-166,215-224,448-493`

**Relevant assumptions:**

2. **Load-bearing:** The denominator is 2024 GDP per capita only: nominal current US dollars or PPP current international dollars, selected by the reader.
3. **Load-bearing:** The displayed rate is `award rows / GDP per capita × 1,000`, labelled “awards per $1,000 GDP per capita”; it is not a total-GDP, population, or distinct-laureate rate.
4. The chart displays the top 15 eligible countries, breaking equal rates by exact dataset country name in ascending order.
5. A country is eligible only with a positive, exact-2024 denominator and at least five recorded award rows, using the same numeric threshold as the existing Explorer rate charts.

**Steps → verify:**

1. Insert the `Awards per GDP per capita` section immediately after the existing country section. Its explanatory note
   says “recorded awards by affiliation country when awarded,” 2024 World Bank GDP-per-capita data, the five-award threshold, and the
   unit “awards per $1,000 GDP per capita.” Add a labelled select, a status paragraph, and a figure with unique IDs.
2. Populate the select in this fixed order: selected `GDP per capita (current US$)`, then `GDP per capita, PPP
   (current international $)`. Do not add total-GDP, population, country-field, or per-person choices.
3. Read `DATA.gdp_per_capita_rankings` and render only its selected pre-ranked list as horizontal bars. Each row shows
   its country and rate to two decimal places; a bar tooltip states country, award-row count, selected denominator,
   2024 unit, and rate. Changing the select clears and redraws only this figure.
4. Give each rendered SVG a measure-specific `<title>` and a `<desc>` containing every retained country’s full count,
   denominator, and rate. For an empty list, clear the figure and put exactly `No countries meet the five-award and
   2024-data requirements for this measure.` in the visible status. Clear that status when results exist.
5. Leave the existing country selector, population-rate views, birth-versus-affiliation flow chart, and all other
   Explorer sections unchanged.
6. Verify manually in a built page that either dropdown view contains no more than 15 labelled bars, status behavior
   works when supplied an empty list, and SVG accessible text changes with the selection.

**Acceptance scenarios covered:** “initial display,” “PPP selection,” and “no eligible country.”

## T4 — Lock the payload, ranking, snapshot, and template contracts with tests

**ID:** T4

**Depends-on:** T1, T2, T3

**Files:** `tests/test_build_website.py:156-263,308-323`

**Relevant assumptions:**

1. **Load-bearing:** “Awards” means one `AwardRecord` per distinct populated affiliation country, so repeat winners contribute one count for each award row and a multi-country award contributes once to each country.
2. **Load-bearing:** The denominator is 2024 GDP per capita only: nominal current US dollars or PPP current international dollars, selected by the reader.
3. **Load-bearing:** The displayed rate is `award rows / GDP per capita × 1,000`, labelled “awards per $1,000 GDP per capita”; it is not a total-GDP, population, or distinct-laureate rate.
4. The chart displays the top 15 eligible countries, breaking equal rates by exact dataset country name in ascending order.
5. A country is eligible only with a positive, exact-2024 denominator and at least five recorded award rows, using the same numeric threshold as the existing Explorer rate charts.

**Steps → verify:**

1. Extend the Explorer fixture snapshot with both maps. Assert the full `gdp_per_capita_rankings` payload, including
   country index, award-row count, denominator, rate, duplicate same-country units, and a multi-country award; retain
   the existing merged-person assertions unchanged.
2. Test the pure ranking helper with more than 15 eligible countries, a PPP order different from nominal, equal rates,
   missing/zero/negative denominators, and a below-five count. Assert top-15 truncation, exact-name ties, unrounded
   rate arithmetic, and exclusions exactly.
3. Open the production static snapshot in a test and assert the two map/source objects, representative reconciled
   names (`Czech Republic`, `South Korea`, `Turkey`), absence of their World Bank aliases, and omission of a country
   that lacks an exact 2024 source value.
4. Extend the Explorer template contract test for section order, exact option labels and nominal default, top-15
   result-list use, the rate scale, SVG title/description, empty-status text, and isolation from existing country and
   population-flow chart code.
5. Verify with `uv run python -m unittest tests/test_build_website.py` that the focused suite passes.

**Acceptance scenarios covered:** all scenarios in the specification.

## T5 — Build and inspect the generated Explorer

**ID:** T5

**Depends-on:** T4

**Files:** generated `website/dist/explorer/index.html` only; it remains untracked.

**Relevant assumptions:**

3. **Load-bearing:** The displayed rate is `award rows / GDP per capita × 1,000`, labelled “awards per $1,000 GDP per capita”; it is not a total-GDP, population, or distinct-laureate rate.
6. The static World Bank snapshot is refreshed manually; the build and browser MUST NOT fetch economic data.

**Steps → verify:**

1. Run `uv run website/build.py --base-url http://localhost:8000/` from `datasets/`; it succeeds without modifying
   `awards.sqlite3`.
2. Parse the built `explorer-data` block: both `gdp_per_capita_rankings` lists have at most 15 entries, each country
   index resolves against `countries`, and the JSON contains no literal `<`.
3. Load `/explorer/` and switch the dropdown. Confirm the nominal and PPP views replace only the new chart, retain all
   15-or-fewer country labels, and preserve the existing country and flow charts.

**Acceptance scenarios covered:** final end-to-end confirmation of “initial display” and “PPP selection.”
