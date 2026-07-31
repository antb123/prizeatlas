## Goals

Add a second country-ranking chart to `/explorer/` that shows the top 15 countries by recorded awards relative to 2024 GDP per capita. The chart MUST offer exactly two denominator choices in a dropdown: nominal GDP per capita and GDP per capita at purchasing-power parity (PPP). It MUST attribute an award to each recorded affiliation country at the time of that award, not total GDP, birth country, population, or a live browser request.

Success is verifiable when a site build embeds two pre-ranked 2024 nominal and PPP GDP-per-capita result lists in the Explorer payload, the chart defaults to nominal GDP per capita, changes to PPP when selected, and each view shows at most 15 eligible countries in descending rate order.

## Background

The existing Explorer country section at `website/templates/explorer.html:150-166` ranks distinct laureates by birth,
death, affiliation, citizenship, and population-normalised birth or affiliation counts. Its population-rate JavaScript at
`website/templates/explorer.html:448-493` counts one merged person per country and requires at least five people. The
page already embeds all chart inputs as JSON (`website/templates/explorer.html:215-224`), so it makes no data request
after loading except the separate optional country-detection request.

`website/build.py:489-582` obtains an existing World Bank population snapshot from
`website/population.json:1-111`, aligns it with the payload's country-index array, and emits the Explorer JSON. The
database has one `AwardRecord` per recorded award row; this new chart deliberately counts those rows rather than the
merged identities used by the pre-existing country chart. The 2024 World Bank indicators are
[`NY.GDP.PCAP.CD` — GDP per capita (current US$)](https://data.worldbank.org/indicator/NY.GDP.PCAP.CD) and
[`NY.GDP.PCAP.PP.CD` — GDP per capita, PPP (current international $)](https://data.worldbank.org/indicator/NY.GDP.PCAP.PP.CD).
Their 2024 API responses are the exact input to snapshot, respectively
[`nominal`](https://api.worldbank.org/v2/country/all/indicator/NY.GDP.PCAP.CD?date=2024&format=json&per_page=400) and
[`PPP`](https://api.worldbank.org/v2/country/all/indicator/NY.GDP.PCAP.PP.CD?date=2024&format=json&per_page=400).

This feature is approximately 110 application/test LOC plus about 150 static-data lines across four implementation
files: `website/build.py:489-582`, `website/templates/explorer.html:150-166,215-224,448-493`,
`website/population.json:1-111`, and `tests/test_build_website.py:156-263,308-323`. It does not change the database,
routes, the existing population charts, or the site's runtime network behaviour.

## Assumptions

1. **Load-bearing:** “Awards” means one `AwardRecord` per distinct populated affiliation country, so repeat winners contribute one count for each award row and a multi-country award contributes once to each country.
2. **Load-bearing:** The denominator is 2024 GDP per capita only: nominal current US dollars or PPP current international dollars, selected by the reader.
3. **Load-bearing:** The displayed rate is `award rows / GDP per capita × 1,000`, labelled “awards per $1,000 GDP per capita”; it is not a total-GDP, population, or distinct-laureate rate.
4. The chart displays the top 15 eligible countries, breaking equal rates by exact dataset country name in ascending order.
5. A country is eligible only with a positive, exact-2024 denominator and at least five recorded award rows, using the same numeric threshold as the existing Explorer rate charts.
6. The static World Bank snapshot is refreshed manually; the build and browser MUST NOT fetch economic data.

## Static 2024 economic snapshot

`website/population.json:1-111` SHALL remain the single static country-metrics file. Its existing `population` object
and `source` string stay intact. Add a `gdp_per_capita_source` object recording the two World Bank indicator codes,
their 2024 date, and fetch date, plus a `gdp_per_capita` object with `nominal` and `ppp` country-name-to-number maps.

The maps MUST contain only exact 2024 values from the two cited indicator responses after explicit reconciliation to
the dataset's current country names. A source country whose 2024 value is missing, zero, non-numeric, or cannot be
unambiguously reconciled MUST be omitted; it cannot appear in the affected ranking. Do not substitute the
most recent earlier value, infer values, include World Bank aggregate regions, or use a per-capita series other than
the two specified indicators. The static file is provenance, not a refresh program: no script or build-time download
is added.

Use this reviewed reconciliation table for both maps; all other stored names must match the World Bank API name
exactly. `Cuba`, `Taiwan`, `Venezuela`, and `Yemen` remain absent unless a future refresh exposes an exact 2024 observation for
each metric.

| Dataset country name | World Bank 2024 API country name |
| --- | --- |
| Bahamas | Bahamas, The |
| Czech Republic | Czechia |
| Democratic Republic of the Congo | Congo, Dem. Rep. |
| Egypt | Egypt, Arab Rep. |
| Hong Kong | Hong Kong SAR, China |
| Iran | Iran, Islamic Rep. |
| Palestine | West Bank and Gaza |
| Puerto Rico | Puerto Rico (US) |
| Russia | Russian Federation |
| Saint Lucia | St. Lucia |
| Slovakia | Slovak Republic |
| South Korea | Korea, Rep. |
| Turkey | Turkiye |
| Vietnam | Viet Nam |

## Payload generation

Extend `website/build.py:489-582` with one small loader for the new nested snapshot maps and one pure ranking helper;
use both only from `explorer_payload`. The existing population loader and its callers, including
`plan_per_capita_places` at `website/build.py:1150-1159`, remain unchanged.

While iterating `records` inside `explorer_payload`, tally every distinct nonblank `AwardAffiliation.country` on each
award row in an insertion-independent country-name counter. A repeated country on units of one award counts once, while
an award with affiliations in multiple countries counts once in each. The tally is independent of QID/person merging.
After existing `people` construction, append to `countries` only any names from that counter not already present, in
exact dataset-country-name order. This preserves all prior country indices and payload values while allowing every
recorded award affiliation to be counted.

For each source map, the pure helper SHALL join those counted country names to its GDP-per-capita value, skip values
that are missing or non-positive and counts below five, calculate `award rows / GDP per capita × 1,000`, sort by
descending unrounded rate then exact dataset country name, and keep the first 15. Its returned entries carry the
country index, award-row count, denominator, and unrounded rate. The payload SHALL add:

```text
gdp_per_capita_rankings: {
  nominal: [{country_idx, award_count, denominator, rate}, ...],
  ppp:     [{country_idx, award_count, denominator, rate}, ...]
}
```

The two ranking arrays contain at most 15 entries and all entry indices MUST address the final `countries` array.
Existing payload keys and their values remain unchanged for pre-existing country indices. JSON serialization continues
through `explorer_json`, preserving its script-closing-character escape. The build does not need a second database
query.

```text
awards.sqlite3 AwardRecord rows                       population.json (static)
         │ tally distinct affiliation countries per award      │ 2024 nominal + PPP per-capita GDP
         └─────────────────────────────┬──────────────────────┘
                                       ▼
           pure ranking helper → two ordered, eligible top-15 result lists
                                       │ embedded JSON
                                       ▼
                         Explorer dropdown → render the selected list
```

## Explorer chart

Insert a new Explorer section immediately after `website/templates/explorer.html:150-166` and before the early-winner
section. It SHALL use the heading `Awards per GDP per capita`, explain that it is based on recipients’ recorded
affiliation country when awarded and 2024 World Bank GDP-per-capita data, and state the five-award eligibility threshold. The section contains
one accessible `<select>` labelled for the GDP-per-capita measure, one status paragraph, and one `<figure>` for the
generated SVG.

The select offers exactly these options, in this order:

1. `GDP per capita (current US$)` — selected initially.
2. `GDP per capita, PPP (current international $)`.

At `website/templates/explorer.html:215-224`, read the new result-list payload field into a JavaScript constant beside
`POPULATION`. Add an isolated chart block after the existing country-chart block at
`website/templates/explorer.html:448-493`; do not change the country selector, the population-rate views, or the
birth-versus-affiliation flow chart.

For the selected pre-ranked list, the chart code SHALL:

- render a labelled horizontal bar for every retained country, show the rate to two decimal places, and expose an SVG
  title and description plus per-bar tooltip giving country, award-row count, selected 2024 GDP-per-capita value, and the rate;
- clear and redraw the same figure on dropdown changes; and
- replace the status text with `No countries meet the five-award and 2024-data requirements for this measure.` if no
  country qualifies, without throwing.

The SVG title MUST identify the selected measure and the description MUST give every retained country's full values
and rate, so the visual's information is available to keyboard and touch assistive technology as well as pointer users.

The visible title, note, option labels, tooltip, and SVG accessibility label MUST say `awards`, `GDP per capita`, and
the applicable nominal or PPP unit. They MUST NOT describe the calculation as laureates, population, total GDP, or
GDP per person beyond the established `GDP per capita` indicator name.

### Requirement: Economic data stays precise and offline — MUST

#### Scenario: complete 2024 values
- WHEN the static snapshot is prepared from either World Bank indicator
- THEN each stored value is an exact 2024 observation under the matching dataset country name
- AND its source metadata identifies the relevant indicator and retrieval date.

#### Scenario: unrepresented country
- WHEN an award affiliation country has no reconciled exact-2024 value for a selected metric
- THEN it does not appear in that metric's result list
- AND the chart skips it without a fallback, inference, or network request.

### Requirement: GDP-per-capita ranking — MUST

#### Scenario: initial display
- WHEN `/explorer/` loads with a payload containing eligible countries
- THEN the new chart defaults to nominal GDP per capita
- AND it displays at most 15 horizontal bars ranked by recorded awards per $1,000 GDP per capita.

#### Scenario: PPP selection
- WHEN the reader selects `GDP per capita, PPP (current international $)`
- THEN the existing bars are replaced with the pre-ranked PPP result list
- AND no existing country-chart selection or other Explorer chart changes.

#### Scenario: minimum and invalid values
- WHEN an award affiliation country has fewer than five award rows, or its chosen denominator is absent or non-positive
- THEN it is excluded from that ranking
- AND the chart remains usable for all eligible countries.

#### Scenario: no eligible country
- WHEN a selected result list is empty
- THEN the figure is cleared
- AND its visible status announces why no ranking is available.

## Tests and verification

Update `tests/test_build_website.py:156-263` so its temporary snapshot contains nominal and PPP GDP-per-capita maps.
The exact expected Explorer payload MUST assert both ranking lists, their country indices, award counts, denominators,
and rates. The fixture MUST include duplicate same-country units and a multi-country award, proving that an award is
counted once per distinct affiliation country while existing merged-person country payload data remains unchanged.

Add focused tests for the pure ranking helper with more than 15 eligible countries, a PPP ordering that differs from
nominal, equal rates, and missing, zero, negative, and below-five inputs. Assert the top-15 cutoff, exact-name tie order,
unrounded computation, and every exclusion. Add snapshot assertions for representative reconciliation aliases
(`Czech Republic`, `South Korea`, and `Turkey`) and omission of a source with no exact 2024 metric.

Update `tests/test_build_website.py:308-323` to keep the section-order contract and to assert the new heading,
dropdown, nominal default, PPP option, result-list consumption, top-15 limit, rate scale, accessible SVG text,
empty-status identifier, and isolated chart identifiers. The test must also guard that the former country and
population-flow code remains present.

Implementation verification is:

1. `uv run python -m unittest tests/test_build_website.py` — the focused suite passes.
2. `uv run website/build.py --base-url http://localhost:8000/` — the static build succeeds without changing SQLite.
3. Parse `website/dist/explorer/index.html`'s `explorer-data` block — each `gdp_per_capita_rankings` list has at most
   15 entries, every country index resolves, the two lists use the intended 2024 unit, and the block has no literal `<`.
4. Open `/explorer/` — both dropdown states show no more than 15 labelled bars, tooltips and accessible descriptions
   show the intended 2024 unit, an empty list exposes its status, and the existing country and flow charts still behave
   as before.

## Compatibility and out of scope

This is a static, additive Explorer enhancement. Existing public routes, the database schema and contents, score
calculation, person identity merging, the country selector, population-based charts, and optional country detection
remain unchanged. The chart is not a claim of causal productivity, a price-adjusted real-GDP series, a historical
year-by-year comparison, a total-GDP chart, a GDP-per-capita chart by itself, or an API.
