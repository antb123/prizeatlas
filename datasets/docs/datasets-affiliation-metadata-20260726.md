## Goals

Add one small affiliation metadata lookup so institution detail pages MAY show an externally hosted logo and curated description without repeating those values on every award row. Phase 1 MUST leave the existing `awards` table shape and affiliation routing behavior intact.

Success means a metadata row is selected only through an exact affiliation Wikidata QID, enriched affiliation pages render its safe nonblank fields, and all existing pages still build when an award or institution has no metadata.

## Background

The live `awards.sqlite3` schema stores affiliation facts directly on each award, including `affiliation_name`, `affiliation_sub_name`, and `affiliation_wikidata_qid`. On 2026-07-26, 1,694 of 3,091 award rows have a nonblank affiliation QID, representing 304 distinct QIDs. Repeating logo URLs and descriptions on those award rows would duplicate institution-level data and permit conflicting copies.

The static website reads `awards` and `award_ranking` in one read-only transaction (`website/build.py:299-344`) and currently groups affiliation pages by stored parent name and derived slug (`website/build.py:463-542`). The detail template has an institution heading and award list but no institution metadata (`website/templates/affiliation.html:3-22`).

Forty-nine award rows contain compound affiliation names, and none currently has an affiliation QID. Fully normalizing award-to-institution relationships requires a junction table and data migration; the user has deferred that database refactor to phase 2.

## Assumptions

1. **Load-bearing:** Phase 1 adds an `affiliations` lookup table but does not alter, split, or migrate any row in `awards`.
2. **Load-bearing:** `affiliations.affiliation_wikidata_qid` is the lookup table primary key and joins only to an exact nonblank `awards.affiliation_wikidata_qid`.
3. The three columns are `affiliation_wikidata_qid`, `logo_url`, and `description`; the display name continues to come from `awards.affiliation_name`.
4. `logo_url` means a direct HTTPS image URL and remains externally hosted; the Wikidata URL is derived from the QID.
5. The lookup is partial: awards without a QID and QIDs without a metadata row continue to render the existing affiliation page.
6. Affiliation page identity, route, display-name selection, ranking, units, and award membership remain name/slug based in phase 1.
7. A page with no matching profile keeps current behavior; a page with a matching profile and any different nonblank QID fails rather than selecting arbitrary metadata.
8. Initial live metadata population is separate curated data work; this feature may ship with an empty table and fixture-only test rows.
9. **Load-bearing:** A metadata QID is eligible for insertion only after every live award row carrying it has been checked as the same real institution; syntactic QID validity alone is insufficient.

## Recommendation

Use a separate table and join by QID. Do not add `logo_url` or `description` to `awards`.

```text
awards.affiliation_wikidata_qid  ──0..1──>  affiliations.affiliation_wikidata_qid
       repeated award facts                    one institution profile
```

This is additive rather than a database refactor: the existing flat award record remains untouched. A phase-2 junction table can later replace semicolon-delimited affiliations without changing the metadata table.

Estimated implementation scope: approximately 90–130 LOC across four files.

| File | Current range | Planned change |
|---|---:|---|
| `awards.sqlite3` | `awards` schema object; binary file has no line range | After a dated backup, add the `affiliations` table only; do not update `awards`. |
| `website/build.py` | `AWARD_COLUMNS` and dataclasses, lines 78-159; database read, lines 299-344; affiliation planning, lines 463-542; site validation/planning, lines 602-656 and 908-975; build entry point, lines 1210-1214 | Read and validate profiles, associate them by exact QID, and pass optional metadata to affiliation pages. |
| `website/templates/affiliation.html` | lines 3-7 | Conditionally render logo, description, official-site link, and Wikidata link. |
| `tests/test_build_website.py` | fixture database, lines 34-65; affiliation-page coverage, lines 717-837 | Add the lookup table fixture and prove QID joins, fallbacks, escaping, and URL rejection. |

No CSS change is planned: the affiliation logo SHALL reuse `.award-logo.award-logo-large` from `website/static/style.css:198-218`.

## Database

The live database MUST be backed up before schema work:

```text
cp awards.sqlite3 awards.sqlite3.$(date +%Y%m%d).bak
```

Add this strict table:

```sql
CREATE TABLE affiliations (
    affiliation_wikidata_qid TEXT PRIMARY KEY,
    logo_url                 TEXT NOT NULL DEFAULT '',
    description              TEXT NOT NULL DEFAULT ''
) STRICT;
```

The implementation SHALL NOT rebuild `awards.sqlite3`, add repeated metadata columns to `awards`, or add a foreign key that would require rebuilding `awards`. The relationship is optional because QID coverage is incomplete and the metadata table is intentionally partial.

After the schema write, `PRAGMA integrity_check;` MUST return exactly `ok`. The implementation SHALL also verify:

- the new table has exactly the three contracted columns;
- `awards` retains its current columns and row count;
- no `awards` value changed;
- every nonblank metadata QID is a syntactically valid Wikidata item ID;
- every metadata QID occurs in at least one live award row and has passed the identity audit in Assumption 9;
- every nonblank `logo_url` is an absolute HTTPS URL with a hostname and no embedded username or password.

The audit MUST report every distinct `(affiliation_wikidata_qid, affiliation_name)` pair for each proposed metadata QID. Aliases are acceptable only after they are verified as the same institution. A QID spanning different institutions is ineligible until the award data is corrected in a separately backed-up data task. In particular, live QID `Q168751` currently appears on both Duke University and University of California, Berkeley rows and MUST NOT receive an `affiliations` row in phase 1.

### Requirement: Additive schema — award records MUST remain unchanged

#### Scenario: Schema creation
- WHEN the phase-1 schema is applied to a backed-up live database
- THEN `affiliations` exists with the three contracted columns
- AND the `awards` schema, row count, and content are unchanged
- AND `PRAGMA integrity_check;` returns `ok`

## Website data flow

Add a small immutable `AffiliationProfile` value with QID, logo URL, and description. `read_database` SHALL read all profile rows in the same explicit read transaction as rankings and awards and return them separately rather than copying profile data into every `AwardRecord`.

The site planner SHALL build one `profiles_by_qid` mapping after validating:

- each QID is nonblank and matches the Wikidata QID contract;
- each QID occurs on at least one live award row;
- duplicate QIDs cannot exist because the table primary key enforces uniqueness;
- nonblank logo URLs pass the existing HTTPS/host/credentials safety contract;
- text fields remain ordinary untrusted display data and are escaped by Jinja.

For each existing name/slug-based affiliation page, collect its distinct nonblank `affiliation_wikidata_qid` values and resolve only those with rows in `profiles_by_qid`:

- zero matching profiles: attach no profile, regardless of how many unenriched QIDs the page contains;
- one matching profile whose QID is the page's only nonblank QID: attach it;
- one matching profile plus any different nonblank page QID, or more than one matching profile: raise `BuildFailure` with the route and conflicting QIDs.

The builder MUST use a left-join policy: a missing profile never removes an affiliation or award page. It MUST NOT fall back to joining by institution name, URL, slug, coordinates, or fuzzy similarity.

### Requirement: Exact identity — metadata MUST attach only by exact QID

#### Scenario: Matching profile
- WHEN an affiliation page's award records have QID `Q13371`
- AND the lookup contains a `Q13371` profile
- THEN that profile is attached to the page

#### Scenario: Missing profile or QID
- WHEN an affiliation has no QID or its QID has no lookup row
- THEN the page renders with its existing heading, counts, and award list
- AND no metadata placeholder is shown

#### Scenario: Conflicting page QIDs
- WHEN one derived affiliation route contains records with two distinct nonblank affiliation QIDs
- AND at least one has a metadata row
- THEN the build fails with the route and both QIDs
- AND it does not select either profile

## Affiliation page

When a profile is attached, `website/templates/affiliation.html` SHALL:

- render `logo_url` as the image source only when nonblank, using the existing large-logo classes and an alt value derived from the escaped affiliation name;
- render the curated `description` only when nonblank;
- render the QID as a link to `https://www.wikidata.org/wiki/{qid}`.

The existing laureate/award count line and award list SHALL remain unchanged. When no profile is attached, the generated markup SHALL be equivalent to the current page apart from inconsequential whitespace.

### Requirement: Conditional presentation — blank metadata MUST create no empty UI

#### Scenario: Complete profile
- WHEN logo URL, description, and QID are present
- THEN the affiliation page shows the logo, description, and Wikidata link

#### Scenario: Partial profile
- WHEN only QID and description are nonblank
- THEN the description and Wikidata link render
- AND no image renders

#### Scenario: Unsafe URL
- WHEN a nonblank logo URL is not safe absolute HTTPS
- THEN the build fails before rendering or promoting the staged site

## Compatibility and failure behavior

The change is backward-compatible with every existing award row and public route. It deliberately does not merge aliases that share a QID; such route and identity changes belong to phase 2. Existing profiles may therefore appear on more than one name-derived page when those pages carry the same QID.

The database remains read-only during website generation. Invalid metadata fails before output promotion, so the existing deployed `website/dist/` survives. Errors SHALL remain concise and identify the operation plus safe QID or affiliation route; they SHALL NOT log descriptions or URLs.

## Verification

Implementation verification MUST include:

1. Back up the database, add the table, and confirm `PRAGMA integrity_check;` is `ok`.
2. Compare `awards` schema, row count, and a table hash before and after the schema change.
3. For every proposed live metadata QID, inspect every distinct attached affiliation name; confirm that no table row is inserted for `Q168751` while its live Duke/Berkeley conflict remains.
4. Confirm every metadata QID occurs on at least one award row.
5. Run `uv run python -m unittest tests/test_build_website.py`.
6. Run `uv run ruff check website/build.py tests/test_build_website.py`.
7. Run `uv run website/build.py --base-url https://example.org/awards/`.
8. Inspect one fixture-built page with complete metadata and one live page without metadata.

## Phase 2 (out of scope)

Phase 2 MAY normalize award affiliations into an institution table plus an award-to-affiliation junction table, split verified compound affiliations, migrate the current affiliation name/location/QID fields, and make QID the page identity. It requires a separate reviewed specification and migration because it changes award data, counts, routes, and multi-affiliation semantics.

## Implementation constraints

Create one branch for this specification, use conventional commits, generate tests alongside implementation, and do not merge until reviewed. Squash-merge into the applicable `YYYYMM` month branch, using a `fix` prefix or `DD` suffix for a smaller fix.
