## CT-1 — Verify every affiliation city from longitude,latitude

ID: CT-1

Depends-on: none

Files: `scripts/check_nominatim_affiliations.py:90-192`; `tests/test_check_nominatim_affiliations.py:1-130`

Assumptions: 1, 3, 6

Steps → verify:

1. Read position 1 and positions 2+ and group every complete trimmed city/country pair, including pairs with missing coordinates.
2. Strictly parse finite WGS84 `longitude,latitude`, check each pair against Nominatim, retain distinct institution points, and report one explicit result per pair.
3. Return nonzero unless verified pairs equal total pairs; unit-test both stores, missing/invalid/reversed values, mismatches, lookup failure, and several valid points in one city.
4. Run `uv run -m unittest tests.test_check_nominatim_affiliations` → all checker tests pass.

## CT-2 — Complete the coordinate evidence

ID: CT-2

Depends-on: CT-1

Files: `awards.sqlite3` (exact rows selected by `award_record_id`; SQLite has no line ranges)

Assumptions: 1, 3, 6

Steps → verify:

1. Back up `awards.sqlite3` with the required `YYYYMMDD` suffix.
2. Run the checker to enumerate city/country pairs with no valid stored point.
3. For each blank, confirm the city through Wikidata and Nominatim, reverse-check `longitude,latitude`, then update only the blank cell guarded by exact `award_record_id`; do not overwrite existing coordinates.
4. Run the checker → verified-pair count equals total-pair count and exit status is zero.
5. Run `sqlite3 awards.sqlite3 "PRAGMA integrity_check;"` → exactly `ok`.

## CT-3 — Plan and generate city routes

ID: CT-3

Depends-on: CT-2

Files: `website/build.py:48-96`, `website/build.py:1206-1260`, `website/build.py:2151-2248`, `website/build.py:2653-2689`, `website/build.py:2827-2872`, `website/build.py:3082-3130`

Assumptions: 1–6

Steps → verify:

1. Add the reserved Cities route and group QID-linked laureates by trimmed city/country across all award affiliations.
2. Require a parseable WGS84 point for every planned pair, deduplicate a laureate within a city, collision-check routes, and sort by count then label.
3. Generate the Cities index/detail jobs, metadata, ItemList, sitemap participation, and `llms.txt` route contract without network access.
4. Exercise a temporary plan with repeated awards, a second affiliation, both Cambridges, differing in-city points, and a missing point → counts and separation are correct, while the missing point raises `BuildFailure`.

## CT-4 — Add Cities navigation and reusable return text

ID: CT-4

Depends-on: none

Files: `website/templates/_view_tabs.html:11-17`; `website/templates/country.html:1-19`

Assumptions: 3, 4

Steps → verify:

1. Add the Cities link and active state without changing the existing four tab destinations.
2. Parameterize the detail return label so existing pages say `All countries` and city pages say `All cities`.
3. Render representative country and city jobs → tab semantics, escaping, and labels are correct.

## CT-5 — Lock the public behavior with website tests

ID: CT-5

Depends-on: CT-3, CT-4

Files: `tests/test_build_website.py:1457-1595`

Assumptions: 1–6

Steps → verify:

1. Add focused fixtures and assertions for deduplication, extra affiliations, deterministic order, Cambridge disambiguation, detail membership, coordinate rejection, active tabs, return labels, and subpath-safe city URLs.
2. Run `uv run -m unittest tests.test_build_website` → all website build tests pass.
3. Run `uv run website/build.py --base-url https://example.org/awards/` → the full static build succeeds after CT-2 and writes city routes beneath the deployment subpath.
