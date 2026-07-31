# TODO — affiliation metadata

Spec: `docs/specs/datasets-affiliation-metadata-20260726.md`

## Shared assumptions

1. Phase 1 adds `affiliations` but does not alter, split, or migrate `awards`.
2. Metadata joins only through exact `affiliation_wikidata_qid`; there is no name, slug, coordinate, or fuzzy fallback.
3. The lookup has exactly three columns: `affiliation_wikidata_qid`, `logo_url`, and `description`.
4. The lookup is partial, and pages without a matching profile retain current behavior.
5. Affiliation page identity, routing, ranking, and membership remain name/slug based.
6. Every live metadata QID must occur in `awards` and pass a manual audit of all attached affiliation names.
7. QID `Q168751` is ineligible while it remains attached to both Duke and Berkeley rows.
8. Compound-affiliation normalization and QID-based page identity are phase 2.

## T1 — Add the lookup table without changing awards

ID: `T1`

Depends-on: none

Files: `awards.sqlite3` (`awards` and new `affiliations` schema objects; binary file has no line ranges)

Steps → verify:

1. Record `sqlite3 awards.sqlite3 ".schema awards"`, the award row count, and `sqlite3 awards.sqlite3 ".sha3sum awards"`.
2. Create a dated backup with `cp awards.sqlite3 awards.sqlite3.$(date +%Y%m%d).bak` → the backup exists before any write.
3. In one short transaction, create the strict three-column `affiliations` table from the spec → `.schema affiliations` matches the contract.
4. Do not insert unaudited live metadata; specifically do not insert `Q168751` → a query for that QID returns zero rows.
5. Re-run the recorded awards schema, row count, and awards-only SHA3 → all three equal their pre-change values.
6. Run `sqlite3 awards.sqlite3 "PRAGMA integrity_check;"` → output is exactly `ok`.

## T2 — Read, validate, and associate profiles by QID

ID: `T2`

Depends-on: `T1`

Files: `website/build.py` (`AWARD_COLUMNS` and dataclasses, current lines 78-159; URL validation, lines 240-244; database read, lines 299-344; affiliation planning, lines 463-542; site validation/planning, lines 602-656 and 908-975; build entry point, lines 1210-1214)

Steps → verify:

1. Add immutable `AffiliationProfile` data and add `affiliation_wikidata_qid` to `AwardRecord`/`AWARD_COLUMNS` → every dataclass field is populated by name from the database.
2. Read all `affiliations` rows within the existing read-only transaction and return profiles separately from award records → no profile fields are copied onto each award record.
3. Validate QID syntax, require every profile QID to occur on an award row, and validate only nonblank `logo_url` values with the HTTPS/hostname/no-credentials contract → invalid fixture values raise concise `BuildFailure` messages without logging URL or description text.
4. Build `profiles_by_qid` once and pass it into affiliation planning → a QID performs one exact dictionary lookup.
5. For each derived page, resolve its record QIDs against the profile map: zero matches attaches no profile; exactly one page QID with one match attaches it; a match plus a different page QID or multiple matches raises with route and QIDs → no arbitrary metadata choice is possible.
6. Leave page grouping, routes, counts, unit nesting, award membership, and ordering unchanged → existing affiliation tests remain behaviorally unchanged.
7. Run `uv run ruff check website/build.py` → clean.

## T3 — Render optional profile fields

ID: `T3`

Depends-on: `T2`

Files: `website/templates/affiliation.html` (current lines 3-7)

Steps → verify:

1. When a profile and nonblank `logo_url` exist, render an image using `.award-logo.award-logo-large` and escaped affiliation-name alt text → no CSS file changes are needed.
2. Render nonblank description as ordinary escaped text.
3. Always render the attached profile QID as a Wikidata link → the URL is constructed from the validated QID.
4. Guard every optional field → a page without a profile, logo, or description has no empty image, link, or placeholder and preserves its current count line and award list.

## T4 — Prove schema, join, fallback, and safety behavior

ID: `T4`

Depends-on: `T1`, `T2`, `T3`

Files: `tests/test_build_website.py` (fixture database, current lines 34-65; affiliation-page coverage, lines 717-837)

Steps → verify:

1. Extend the fixture database with the three-column strict `affiliations` table and optional profile rows → all existing callers create a compatible database.
2. Add a matching-QID case with complete metadata → generated page includes logo, escaped description, and Wikidata link.
3. Add no-QID and missing-profile cases → existing page content renders and no metadata placeholder appears.
4. Add a partial-profile case → only description and Wikidata link render.
5. Add a page with several unenriched QIDs → it renders normally, proving an empty/partial table is deployable.
6. Add a page with a matched profile plus a different nonblank QID → build raises with the route and both QIDs.
7. Add orphan QID, malformed QID, unsafe logo URL, and hostile description cases → invalid identities/URLs fail, while description markup is escaped.
8. Run `uv run python -m unittest tests/test_build_website.py` → all tests pass.
9. Run `uv run ruff check website/build.py tests/test_build_website.py` → clean.

## T5 — End-to-end verification

ID: `T5`

Depends-on: `T1`, `T2`, `T3`, `T4`

Files: none

Steps → verify:

1. Run `sqlite3 awards.sqlite3 "PRAGMA integrity_check;"` → exactly `ok`.
2. Report every distinct `(affiliation_wikidata_qid, affiliation_name)` pair for each proposed live profile, verify each identity manually, and omit every conflict → `Q168751` remains absent while its Duke/Berkeley conflict exists.
3. Run `uv run website/build.py --base-url https://example.org/awards/` → build completes without modifying `awards.sqlite3`.
4. Inspect one fixture page with complete metadata and one live page without metadata → conditional rendering matches the spec.
5. Confirm the pre/post `awards` schema, row count, and awards-only SHA3 are identical → phase 1 made no award-data refactor.

## Delivery

Create one branch for the specification, use conventional commits, and do not merge until reviewed. Squash-merge into the applicable `YYYYMM` month branch, using a `fix` prefix or `DD` suffix for a smaller fix.
