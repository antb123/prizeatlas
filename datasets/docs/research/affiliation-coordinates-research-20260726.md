# Affiliation-coordinate research handoff

Date: 20260726

Status: research only. No transaction was opened and no values in `awards.sqlite3` were changed during this work. No website code, templates, tests, or configuration were changed.

## Durable evidence

- Raw Nominatim responses: `docs/affiliation-coordinates-nominatim-20260726.json`
- Raw-response SHA-256: `2dcf71ed672f4bb469ff6414299325ffea78f98f82d06ebd49a501ce8d4d5c03`
- The JSON contains the QID, recorded institution name, city, country, and complete response for each of 73 requests.
- The original temporary cache was `/tmp/nobel-nominatim.8fYVfB/`; the JSON above is the durable copy.
- Nominatim use followed its public policy: one thread, no more than one request per second, an identifying User-Agent, and local caching.

## Confirmed scope

The correct missing-coordinate count is 1,313:

```sql
SELECT COUNT(*)
FROM awards
WHERE TRIM(COALESCE(affiliation_name, '')) <> ''
  AND TRIM(COALESCE(affiliation_coordinates, '')) = '';
```

An earlier result of 1,312 was wrong because it did not treat `NULL` as blank.

A broad reuse audit divided the 1,313 rows as follows:

| Class | Rows | Meaning |
|---|---:|---|
| Existing single coordinate for the same nonblank institution QID | 161 | Candidate for reuse, subject to campus/place review |
| Existing single coordinate for the same institution name, after QID candidates | 143 | Candidate for reuse, subject to place review |
| Nonblank QID with no reusable coordinate | 172 | Covers 81 distinct QIDs requiring lookup |
| No QID and no reusable coordinate | 837 | Covers 574 distinct name/country combinations |

A stricter key using exact `affiliation_name`, `affiliation_sub_name`, `affiliation_city`, and `affiliation_country` found 122 blank rows with an existing single coordinate. A further 18 rows matched the same QID, city, and country. These are review candidates, not authorization for an automatic update.

## The six apparent name conflicts

Four conflicts are legitimate campus distinctions now made explicit by `affiliation_sub_name` and `affiliation_city`. Their coordinates should not be collapsed to the parent institution's point:

| Parent name | Parent/main-campus coordinate | Constituent unit | Unit coordinate |
|---|---|---|---|
| Cornell University | `-76.4839,42.4492` (Ithaca) | Weill Cornell Medical College, New York | `-73.9541,40.7645` |
| Harvard University | `-71.1169,42.3744` (Cambridge) | Harvard Medical School, Boston | `-71.1039,42.3369` |
| Johns Hopkins University | `-76.6206,39.3289` | School of Medicine, Baltimore | `-76.5942,39.2989` |
| Yale University | `-72.9267,41.3111` | School of Medicine, New Haven | `-72.9339,41.3032` |

Nominatim independently located Harvard Medical School and Weill Cornell at the recorded unit campuses. A Yale School of Medicine text search returned an unrelated school with a similar name, demonstrating why name similarity alone must not be accepted.

The two actual consistency repairs identified are:

1. Institute of Genetics and Molecular and Cellular Biology (`Q3152004`) has `7.7412,48.5262` and `7.7415,48.5257`. The local QID lookup returns the canonical dataset value `7.7412,48.5262`: <https://www.wikidata.org/wiki/Q3152004>. Nominatim places the same institute within roughly 40 metres and supports the identity, but its feature centroids vary.
2. Cambridge is an identity error as well as a coordinate conflict; see the next section.

## Cambridge identity collision

- `Q35794` is the University of Cambridge and resolves to `0.1132,52.2054`: <https://www.wikidata.org/wiki/Q35794>.
- `Q350` is the city of Cambridge and resolves to `0.1225,52.2081`: <https://www.wikidata.org/wiki/Q350>.
- Three rows named `Cambridge University` already carry the correct university QID and coordinate.
- Fifty rows named `University of Cambridge` carry the city QID `Q350`.
  - Ten of those already have the university coordinate `0.1132,52.2054`.
  - Forty have the city coordinate `0.1225,52.2081`.

The evidence supports normalizing the three aliases to `University of Cambridge`, assigning `Q35794` to all University of Cambridge rows, and using `0.1132,52.2054`. This is a correction of existing nonblank values, so it must be performed as an explicit repair rather than a blank-only enrichment.

## High-confidence new coordinate candidates

These candidates either matched the exact QID stored in the row through Nominatim's `extratags.wikidata`, or were independently returned by the local Wikidata lookup:

| QID | Recorded institution/place | Candidate coordinate | Notes |
|---|---|---|---|
| `Q1153275` | RIKEN, Wako, Japan | `139.6160,35.7788` | Exact OSM QID match. Does not authorize the separate Kobe row. |
| `Q1204921` | International Rice Research Institute, Los Baños, Philippines | `121.2616,14.1417` | Exact OSM QID match. |
| `Q1452369` | Fred Hutchinson Cancer Research Center, Seattle | `-122.3307,47.6278` | Exact OSM QID match across Seattle spelling variants. |
| `Q30256699` | BioNTech, Mainz, Germany | `8.2714,49.9878` | Exact OSM QID match. |
| `Q3152167` | Institut Imagine, Paris, France | `2.3181,48.8453` | Local Wikidata lookup and Nominatim agree. |
| `Q5123723` | City of Hope National Medical Center, Duarte, United States | `-117.9731,34.1280` | Exact OSM QID match. |
| `Q319239` | Tel Aviv University, Tel Aviv, Israel | `34.8050,32.1125` | Exact Wikipedia-title/Wikidata lookup; three blank rows were found. |

Pending rather than accepted:

- Leipzig University (`Q154804`) returned two OSM features carrying the same QID: a faculty at `12.3909,51.3274` and the main university feature at `12.3786,51.3385`. The main feature appears appropriate, but this was not committed as a final decision.
- University of Washington (`Q219563`) returned `-122.3002,47.6554` from OSM while existing curated rows use `-122.3081,47.6542`. Do not overwrite the existing point without choosing and documenting the canonical feature.
- Rockefeller University, NIH, Columbia University, and the Institute for Advanced Study returned exact-QID OSM points close to, but not identical with, existing curated points. The existing values should remain authoritative for internal reuse unless a separate correction audit establishes otherwise.

## QIDs that must not drive coordinates

The unresolved-QID pass exposed incorrect, generic, historical, or overly broad identities. Examples:

- `Q184478`, University of California: a system-level point cannot represent rows from Berkeley, Los Angeles, San Diego, San Francisco, Irvine, and Santa Barbara.
- `Q11087599`: recorded as a Swiss institute but identifies an institute in Prague.
- `Q111722916`: identifies a college in Imphal, not the recorded United States affiliation.
- `Q18627472`: identifies a family name, not DuPont.
- `Q414147`: generic "academy of sciences".
- `Q4894094`: a disambiguation page, not the University of Bern.
- `Q52607919`: Innsbruck University Press, not the university.
- `Q85413125`: a given name, not DESY.

Rows with these identities must remain without coordinates until their institution QID is corrected and the recorded city/country is verified. The University of California parent, RIKEN, Howard Hughes Medical Institute, and other multi-site organizations must be resolved at the recorded campus or unit level rather than assigned a headquarters point indiscriminately.

## Safe continuation point

When an affiliation has no organization QID but its recorded city and country are independently verified, a city-level
`longitude,latitude` coordinate is permitted. It represents the recorded locality, not the organization's exact premises,
and must not be copied from another same-named affiliation. The no-QID coordinate validator must permit this documented
exception.

### 20260728: reviewed no-QID city points

Nominatim returned the following city-level points for reviewed affiliations without an organization QID. Each value is
stored in `longitude,latitude` order and is deliberately a locality point rather than an asserted office, laboratory, or
campus address.

| Affiliation | Recorded city/country | Coordinate |
|---|---|---|
| Alphanosos | Riom, France | `3.1140583,45.8930120` |
| Animal Biotechnology Cambridge Ltd. | Cambridge, United Kingdom | `0.1391537,52.1975846` |
| Atomic Tags, Inc. | La Jolla, United States | `-117.2575702,32.8458529` |
| Farms of Texas Company | Alvin, United States | `-95.2441009,29.4238472` |
| HelpMate Robotics Inc. | Danbury, United States | `-73.4540111,41.3948170` |
| Intermetallics Co., Ltd. | Kyoto, Japan | `135.7681441,35.0115754` |
| Maiman Associates | Marina del Rey, United States | `-118.4486470,33.9776848` |
| Maiman Associates | Los Angeles, United States | `-118.2427660,34.0536909` |
| Molecular Geriatrics Corporation | Vernon Hills, United States | `-87.9649487,42.2373152` |
| Optoelectronics Technology Research Laboratory | Tsukuba, Japan | `140.0772790,36.0833265` |
| Physicomedical Institute | Minneapolis, United States | `-93.2654692,44.9772995` |

Before any database write:

1. Re-read the live rows because `awards.sqlite3` already contained unrelated uncommitted user changes when research began.
2. Separate explicit corrections (Cambridge and IGBMC) from blank-only enrichment.
3. Review every candidate against the row's institution, unit, city, and country. Exclude compound affiliations containing several institutions.
4. Back up the database.
5. Use exact `award_record_id` targets and guard every blank enrichment with `TRIM(COALESCE(affiliation_coordinates, '')) = ''`.
6. Keep the write transaction short.
7. Run `PRAGMA integrity_check;` and `scripts/check_coordinates.sql`.

No SQL update statement was executed during this research.
