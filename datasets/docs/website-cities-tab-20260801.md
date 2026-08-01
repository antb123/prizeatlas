## Goals

- The Countries section MUST add a `Cities` tab at `/countries/cities/` that ranks verified present-day award-time affiliation cities by distinct laureates, highest first.
- Each ranked city MUST link to a static detail page listing its laureates, and city identity MUST include the recorded country so same-named cities remain separate.
- Every displayed city MUST be checked from a stored WGS84 `longitude,latitude` against its city and country before release.
- Success means coordinate verification covers every city/country pair and a full website build produces correct city rankings, links, active-tab state, metadata, sitemap entries, and base-subpath-safe relative URLs.

## Background

The static builder already reads every primary and extra `AwardAffiliation`, merges award rows into QID-identified `Laureate` objects, and generates the Countries views plus institution-by-country pages. `website/build.py:48-96`, `website/build.py:1206-1260`, `website/build.py:1455-1511`, `website/build.py:2151-2306`, and `website/build.py:2653-2689` are the relevant planning and assembly paths. The shared navigation is in `website/templates/_view_tabs.html:11-17`; `website/templates/countries.html:1-22` and `website/templates/country.html:1-19` already provide the required ranked index and laureate list.

The live database has 350 distinct nonblank affiliation city/country pairs and six city names used in more than one country. Five pairs have no stored coordinate and 19 have at least one affiliation row without one. Different institutions in one city legitimately have different coordinates, so equality of coordinates is not a city identity rule. `docs/datasets-affiliation-records-20260728.md:50-91` defines affiliation coordinates as verified `longitude,latitude`; `scripts/check_nominatim_affiliations.py:90-192` currently checks only coordinate-bearing position-1 rows and never fails on discrepancies, so it cannot yet prove complete city coverage.

## Assumptions

1. **Load-bearing:** “Affiliated cities” means the `affiliation_city` and `affiliation_country` recorded on any award-time affiliation row, including `award_extra_affiliations`.
2. **Load-bearing:** Ranking counts distinct laureates with a nonblank `laureate_wikidata_qid`, matching the existing generated country/person pages; rows without a confirmed QID are excluded rather than merged by name.
3. **Load-bearing:** A city is identified by the trimmed `(affiliation_city, affiliation_country)` pair; both values are required, and the display label is `City, Country`; coordinates verify that identity but do not replace it.
4. The Cities index lists every qualifying city in rank order; “top cities” describes the ordering, not a new arbitrary row cap.
5. A laureate may count once in each city where an affiliation was recorded, but never more than once in the same city.
6. **Load-bearing:** Every city/country pair must have at least one stored, parseable WGS84 `longitude,latitude`; institution-specific coordinates within the same city may differ.

## City planning and routes

`website/build.py:48-96`, `website/build.py:1206-1260`, `website/build.py:2151-2248`, `website/build.py:2653-2689`, `website/build.py:2827-2872`, and `website/build.py:3082-3130` SHALL:

- Reserve `cities` beneath `/countries/` and define `/countries/cities/` as the index route.
- Derive city membership from each planned laureate's awards and all of each record's affiliations. Deduplicate the same laureate within each `(city, country)` pair before ranking.
- Refuse to plan a city whose pair has no stored coordinate, or whose stored coordinate is not one finite `longitude,latitude` within WGS84 bounds. External city/country verification remains a pre-release check, not a network request during the static build.
- Reuse `Place` for city rows and the existing country index/detail templates. City routes SHALL be collision-checked lowercase slugs under `/countries/cities/{city-country}/`; a collision MUST fail the build instead of overwriting output.
- Sort cities by descending laureate count, then `City, Country` ascending. Sort each city's laureates by the existing country-detail ordering.
- Generate the index, one detail page per city, `ItemList` structured data subject to `ITEM_LIST_CAP`, ordinary sitemap inclusion, and an `llms.txt` URL-pattern entry.
- Explain in page copy that these are verified award-time affiliation locations, that missing city, country, or coordinates are excluded by the contract, and that laureates can appear in multiple cities.
- Generate an empty but valid Cities index when no complete affiliation city/country pair exists; no division or indexing error may occur.

### Requirement: Ranking — The builder MUST rank distinct laureates by complete affiliation city/country pair
#### Scenario: repeated and additional affiliations
- WHEN  one QID-linked laureate has multiple awards or institutions in one city and an extra affiliation in another city
- THEN  the laureate contributes one count to the first city and one count to the second city
- AND   the city rows remain ordered by count, then label

### Requirement: City identity — Same-named cities in different countries MUST remain separate
#### Scenario: two Cambridges
- WHEN  records contain Cambridge affiliations in the United States and the United Kingdom
- THEN  the index contains two separately counted labels and links
- AND   each detail route lists only laureates attached to that city/country pair

## Coordinate verification

`scripts/check_nominatim_affiliations.py:90-192` and `tests/test_check_nominatim_affiliations.py:1-130` MUST become the release check for city coverage:

- Read both the position-1 affiliation columns in `awards` and positions 2+ in `award_extra_affiliations`, then group complete labels by trimmed city/country pair.
- Parse stored values strictly as finite WGS84 `longitude,latitude`; never accept latitude/longitude order, prose, multiple points, or out-of-range values.
- Check every distinct pair, including pairs with no coordinate. Use the stored point as the Wikidata-derived evidence and Nominatim city/country lookup as the independent check required by the dataset policy. Multiple institution points within a city MAY differ and SHALL be assessed against that city rather than compared for equality.
- Emit a grep-able summary and JSON details with city, country, stored point, result, and reason. Exit nonzero for missing/invalid coordinates, city/country mismatch, lookup failure, or any unchecked pair; exit zero only when verified-pair count equals total-pair count.
- Cache lookup responses as today and never run this network check from `website/build.py`.

Before enabling the route, fill the five currently coordinate-less city pairs in `awards.sqlite3` using the documented Wikidata plus Nominatim lookup sequence, blank-only guarded updates by exact `award_record_id`, a dated backup, `PRAGMA integrity_check`, and the coordinate checker. No existing coordinate may be overwritten merely to make verification pass.

### Requirement: Coordinate gate — Every published city MUST have verified longitude,latitude evidence
#### Scenario: missing, invalid, or mismatched point
- WHEN  a complete city/country pair has no point, a non-WGS84 point, reversed values, or a point that does not verify to the named city and country
- THEN  the coordinate check exits nonzero and identifies the pair and reason
- AND   the static builder refuses a pair with no parseable stored point

#### Scenario: several institutions in one city
- WHEN  institutions in one city have different valid longitudes and latitudes within that city
- THEN  verification accepts the city/country pair without forcing one shared institution coordinate
- AND   the ranking still merges membership by city/country label

## Navigation and detail-page wording

`website/templates/_view_tabs.html:11-17` SHALL add `Cities` as a normal country-view tab, mark it current on both the city index and city detail pages, and preserve the existing Born, Awarded, Died, and Institutions links.

`website/templates/country.html:1-19` SHALL replace the hard-coded `All countries` return-link text with a supplied view label. Existing country jobs MUST continue to render `All countries`; city jobs MUST render `All cities`. No CSS change is expected.

### Requirement: Navigation — The Cities view MUST behave like the existing country views
#### Scenario: subpath build
- WHEN  the site is built with a deployment subpath in `--base-url`
- THEN  every Countries tab, city row, detail-page return link, canonical URL, and sitemap URL resolves beneath that subpath
- AND   the active Cities tab exposes `aria-current="page"`

## Tests

`tests/test_build_website.py:1457-1595` MUST add focused coverage that builds a temporary database containing repeated awards, a second affiliation, valid `longitude,latitude`, same-named cities in different countries, and a city with no coordinate. Assertions SHALL verify distinct-laureate counts, deterministic order, pair disambiguation, detail membership, the missing-coordinate failure, active-tab and return-link wording, and generated city URLs. The coordinate-checker tests MUST cover both affiliation stores, coordinate order/ranges, lookup mismatch/failure, differing valid institution points, complete summary counts, and exit status. The existing website and checker test modules plus a representative full static build MUST pass.

## Compatibility, data, and delivery

- This adds no schema or migration. The only data edits are blank-only coordinate completions needed to make all 350 current city/country pairs verifiable; generated `website/dist/` and checker report/cache files remain unversioned.
- Jinja autoescaping and the existing `href`, `public_url`, route-uniqueness, and sitemap paths MUST remain the only rendering and URL mechanisms.
- Expected implementation scope: 7 files and approximately 140–210 changed lines: `website/build.py`, `website/templates/_view_tabs.html`, `website/templates/country.html`, `tests/test_build_website.py`, `scripts/check_nominatim_affiliations.py`, `tests/test_check_nominatim_affiliations.py`, and `awards.sqlite3`.
- Follow the repository instruction to work on the current branch; do not create a feature branch. Add unit tests with the implementation, use a conventional commit if a commit is requested, and do not merge unreviewed work.
