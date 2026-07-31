# uMap winner location GeoJSON

## Goals

The dataset MUST export two deterministic GeoJSON `FeatureCollection` files suitable for separate uMap layers:
winner birthplaces and winner affiliations.

Each point SHALL expose source properties to filter or style by winner, tier, award, year, country, and the relevant
location fields. Institution filtering applies to the affiliation layer only. No output invents a generic
`location_name` field.

## Background

`awards.sqlite3` stores coordinates as `longitude,latitude` text. Coordinate enrichment is active, so feature counts
MUST be derived from the database snapshot used by each export rather than hard-coded. Some affiliation rows contain
multiple semicolon-separated coordinate pairs and therefore produce multiple points.

All coordinate pairs inspected during drafting are finite and within GeoJSON longitude/latitude bounds. Some birth
points have a blank `birth_city`; the exporter must preserve those blanks rather than invent a value. `award_ranking`
provides the prize score and official URL for all 14 award families.

Source affiliation fields are not uniformly clean. For example, `fields-000017` appears to have an incorrect city
and country; the exporter preserves those values verbatim rather than repairing them.

There is no existing GeoJSON exporter. `AGENTS.md:35-62` defines the database as the source of truth and requires
read-only tools to run from `datasets/`.

## Assumptions

1. **Load-bearing:** Birthplaces and affiliations are separate files and separate uMap layers.
2. **Load-bearing:** Every nonblank coordinate pair becomes one GeoJSON `Point`; missing coordinates produce no feature.
3. **Load-bearing:** Tier 1 is score 90-100, tier 2 is 75-89, and tier 3 is below 75.
4. **Load-bearing:** Multiple affiliation coordinate pairs create multiple point features with repeated award properties.
5. Existing blank descriptive fields remain blank; the exporter does not infer or repair source data.
6. The command is synchronous because a few thousand in-memory point features do not justify concurrency.

## Scope

Three implementation files, approximately 360 lines:

| File | Current line range | Change |
| --- | --- | --- |
| `scripts/export_winner_geojson.py` | new file, lines 1-175 | Validate, join, and export both GeoJSON layers. |
| `tests/test_export_winner_geojson.py` | new file, lines 1-165 | Coordinate, property, tier, multiple-point, and failure tests. |
| `AGENTS.md` | existing lines 35-62 | Document the export command, outputs, tiers, and source limitations. |

The generated `.geojson` files are build artifacts and MUST NOT be committed.

## Command and outputs

The standard-library-only command is:

```text
uv run scripts/export_winner_geojson.py --output-dir <output-directory>
```

`--output-dir` is required and is created when absent. The command creates:

```text
<output-directory>/winner-birthplaces.geojson
<output-directory>/winner-affiliations.geojson
```

The output directory MAY be any explicit path; the exporter MUST NOT assume that the static website exists.

## GeoJSON contract

Both documents MUST be valid RFC 7946 `FeatureCollection` objects whose features are sorted by `award_record_id`,
then coordinate index. Each item in `features` MUST have exactly this top-level structure:

```text
{
  "type": "Feature",
  "id": <stable string>,
  "geometry": {"type": "Point", "coordinates": [<longitude>, <latitude>]},
  "properties": {<contracted properties>}
}
```

Geometry coordinates MUST be numeric `[longitude, latitude]` arrays. The stable IDs defined below MUST use the
top-level GeoJSON `id`, not a property.

Every feature has these properties:

| Property | Source |
| --- | --- |
| `award_record_id` | `awards.award_record_id` |
| `full_name` | `awards.full_name` |
| `year` | `awards.year` |
| `category` | `awards.category` |
| `prize_name` | `award_ranking.prize_name` |
| `award_wikidata_qid` | `awards.award_wikidata_qid` |
| `score` | `award_ranking.score` |
| `tier` | derived from score using assumption 3 |
| `prize_url` | `award_ranking.url` |

Birthplace features additionally contain only:

- `birth_city`;
- `birth_country`.

Affiliation features additionally contain only:

- `affiliation_name`;
- `affiliation_city`;
- `affiliation_country`.

The properties MUST NOT contain `location_name`, `name`, motivations, biographies, raw coordinate strings, or fields
from the other location type.

Feature IDs are stable:

```text
{award_record_id}:birth
{award_record_id}:affiliation:{one-based-coordinate-index}
```

The repeated affiliation features for a multi-coordinate row retain the complete existing `affiliation_name`,
`affiliation_city`, and `affiliation_country` values. The exporter MUST NOT attempt to split prose and associate an
institution name with an individual coordinate. uMap therefore sees semicolon-joined country and institution values
as combined filter values on those rows, not as separate per-point values.

## Coordinate parsing

The parser MUST:

1. split affiliation coordinate strings on semicolons and treat each segment as one point;
2. require birth coordinate strings to contain exactly one point;
3. split each point on one comma into longitude and latitude;
4. parse both values as finite floats;
5. require longitude from -180 through 180 and latitude from -90 through 90;
6. preserve negative and zero values;
7. fail the entire export, naming only the safe `award_record_id`, if any nonblank coordinate is invalid.

All rows and both documents MUST be validated and serialized in memory before any output is published. Each complete
document is written to an adjacent temporary file and promoted with `os.replace`, giving per-file atomicity. A
validation or serialization failure MUST leave both existing output files unchanged; the exporter does not promise
cross-file atomicity for a filesystem failure during the two final replacements.

## Data access and failure behavior

The exporter performs one `LEFT JOIN` from `awards` to `award_ranking` using `award_wikidata_qid`. It MUST explicitly
validate the joined ranking fields and fail when a mapped award lacks a ranking row, score, prize name, or official
URL; an inner join that silently drops rows is forbidden.

The exporter MUST NOT modify the database, enrich missing coordinates, call a network service, or skip malformed
nonblank coordinates. Success logs report only the operation and feature counts. Failure logs identify the operation
and safe record ID without logging coordinate values, caller-supplied filenames, or source prose.

## Acceptance

### Requirement: Birthplace layer — every valid birth coordinate MUST produce one point

#### Scenario: current database snapshot
- WHEN the exporter runs against an `awards.sqlite3` snapshot
- THEN `winner-birthplaces.geojson` contains one point for every row with nonblank valid birth coordinates
- AND a row with a blank `birth_city` retains an empty `birth_city` property

### Requirement: Affiliation layer — every affiliation coordinate pair MUST produce one point

#### Scenario: multiple institutions
- WHEN an affiliation coordinate string contains two semicolon-separated pairs
- THEN two point features are emitted with coordinate indexes 1 and 2 in their IDs
- AND both retain the source affiliation fields without `location_name`

#### Scenario: current database snapshot
- WHEN the exporter runs against an `awards.sqlite3` snapshot
- THEN `winner-affiliations.geojson` contains one point for every semicolon-delimited affiliation coordinate pair
- AND every feature geometry is a GeoJSON `Point`

### Requirement: Tier filtering — every feature MUST carry exactly one derived tier

#### Scenario: boundary scores
- WHEN scores are 90, 89, 75, and 74
- THEN their tiers are 1, 2, 2, and 3 respectively

### Requirement: Invalid data — malformed nonblank coordinates MUST fail the complete export

#### Scenario: out-of-range longitude
- WHEN a fixture contains longitude 181
- THEN the command returns status 1 and names the record ID
- AND neither previous output file changes

### Requirement: Complete ranking join — missing prize metadata MUST fail rather than drop features

#### Scenario: missing ranking row
- WHEN a coordinate-bearing fixture award has no matching `award_ranking` row
- THEN the command returns status 1 and names the record ID
- AND neither output is published

### Requirement: Minimal properties — outputs MUST use existing explicit location fields

#### Scenario: property inspection
- WHEN either output is decoded
- THEN every item has top-level `type`, `id`, `geometry`, and `properties`
- AND no feature contains a `location_name` or `name` property
- AND no birthplace feature has affiliation fields or affiliation feature has birth fields

## Verification

Implementation is complete when:

1. `uv run python -m unittest tests/test_export_winner_geojson.py` passes from `datasets/`.
2. export to a temporary directory produces valid JSON with top-level type `FeatureCollection`.
3. each output count equals its source-row or coordinate-pair count from the same database snapshot.
4. every geometry is `Point`, every coordinate is in bounds, and every feature has a tier from 1 through 3.
5. `tests/test_export_winner_geojson.py` proves neither output contains a `location_name` or `name` property.
6. the SHA3 of the `awards` and `award_ranking` tables is unchanged before and after export.
7. both files import into separate uMap layers and expose prize, tier, year, country, and affiliation filters.

## Delivery constraints

- Create one branch for this specification.
- Use conventional commits and generate unit tests with the implementation.
- Do not merge until reviewed.
- Squash-merge into the `202607` month branch.

## Out of scope

Coordinate enrichment, institution-name parsing, aggregation, clustering configuration, heat maps, marker styling,
website pages, JavaScript maps, database writes, and uMap hosting are out of scope.
