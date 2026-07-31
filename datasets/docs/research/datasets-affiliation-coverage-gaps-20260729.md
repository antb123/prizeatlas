# Affiliation coverage gaps — 20260729

This is a live-state census of affiliation coverage in `datasets/awards.sqlite3`, measured on 2026-07-29.  It explains
which missing values are research work, and which omission a visitor sees on the static website.  It does not authorize
database changes.

`affiliation_name` is the parent institution at the time of the award.  The primary affiliation lives in `awards`; second
and later affiliations live in `award_extra_affiliations`.  Every count below combines both stores.

## What "does not appear" means

The website treats the three fields independently:

```
affiliation name ──> award-page link and affiliation ranking/page
coordinates      ──> affiliation marker on the map
Wikidata QID     ──> stable institution identity and optional profile metadata
```

A QID is not required for an affiliation name to appear on an award page or in the affiliation ranking.  Likewise, a
named affiliation without coordinates still has a page; it is absent only from the map.  A blank name has neither a
link/ranking entry nor a map marker.

`Freelance` is a special historical case: `website/build.py` excludes it from links and rankings because it is not an
institution.  It is **not** a blank-name record.  The current database contains zero `Freelance` rows, so the blocklist
does not change the current counts.  Do not use `Freelance`, a job title, or a prose career note as an institution name.

## Live coverage

| State | Entries / records | Visitor-visible result | Backlog interpretation |
|---|---:|---|---|
| No named affiliation | 340 records | No affiliation link, ranking entry, or map marker | The award source supplies no institution, the recipient is not being represented by an institution, or the research has not yet found an award-time institution.  Do not infer one from a later career. |
| Named affiliation, no QID | 69 entries | Still appears by name; 53 are already on the map | The name needs a verified parent-institution QID.  Some are companies or small/start-up organizations without an English Wikipedia article; others are legacy bodies, public roles, or malformed multi-employer strings.  A missing QID is not proof that the institution has no QID. |
| Named affiliation, no coordinates | 66 entries | Appears by name, but no map marker | Map-coverage gap.  All 66 already have a city and country; resolve a verified point before writing coordinates. |
| Missing both QID and coordinates | 16 entries | Appears by name only; no profile identity or map marker | Resolve the institution identity first, then validate its coordinates. |
| Has coordinates, no QID | 53 entries | Appears by name and on the map; no stable institution identity | Often a company, start-up, role, or institution with no English-Wikipedia route, but each row still needs an exact Wikidata check.  Retain the verified coordinates even if no QID can be established. |
| Has QID, no coordinates | 50 entries | Appears by name and can join to its QID profile, but no map marker | The clearest coordinate-fix queue: use the established QID plus city/country, then confirm the point with Wikidata and Nominatim. |
| Has QID and coordinates | 2,721 entries | Fully linkable and mappable | No coverage action. |

The 340 records with no named affiliation are concentrated in Nobel Literature (122), Nobel Peace (139), Wolf Prize Arts
(58), and Kyoto Prize Arts and Philosophy (19).  That distribution is consistent with award families that often do not
publish a research-employer affiliation, but individual records still need source-based treatment rather than a blanket
assumption.

### Documented exception: the 2016 LIGO contributor group

`breakthrough-000051` is intentionally blank for every affiliation field.  It represents the organizational laureate
"Contributors who are authors of the paper *Observation of Gravitational Waves from a Binary Black Hole Merger* and
contributors who also made important contributions to the success of LIGO," not one employer.  The official announcement
separates the three founders (and names Caltech or MIT for each) from 1,012 contributors drawn from the many institutions
in LIGO and Virgo.  The current row is the contributor group; the three founders are separate award rows with their own
affiliations.  See [Breakthrough Prize's 2016 announcement](https://breakthroughprize.org/News/32).

Assigning this group to LIGO, Caltech, MIT, or any contributor's employer would falsely turn a multi-institution
collaboration into one institution.  Therefore the blank is deliberate: it is not an affiliation-enrichment candidate,
and its Organization classification and blank personal biography fields are correct.

### Documented exception: artists and writers without an associated institution

For artists, composers, filmmakers, and writers, a blank affiliation is often correct rather than incomplete.  Their
award is for creative work, and the award source may not identify an award-time institution.  Do not invent one from a
gallery, publisher, school, venue, former employer, or later appointment.  This explains much of the blank-affiliation
concentration in Kyoto Prize Arts and Philosophy, Wolf Prize Arts, and Nobel Literature, but does not authorize assuming
that every blank in those categories is intentional; retain a blank unless the source names the institution.

### Documented exception: Peace Prize recipients without an associated institution

For Nobel Peace Prize recipients, a blank affiliation is often correct rather than incomplete.  Peace work may be
personal advocacy, diplomacy, political leadership, or humanitarian action rather than employment by one institution;
an organization may also be the laureate itself.  Do not substitute a government office, political party, campaign,
later employer, or associated organization.  This explains much of the Nobel Peace concentration, but the same rule
applies: record an affiliation only when the award source identifies an award-time institution.

### Documented exception: Betty Ford

`lasker_awards-000293` (Betty Ford) is intentionally affiliation-blank.  The Lasker Foundation records her 2000 Public
Service Award for awareness, education, and treatment for substance abuse, not as recognition of work at a named
institution.  Its [2000 winners page](https://laskerfoundation.org/winners/2000-winners/) identifies the award and
citation but supplies no award-time affiliation.  Do not substitute the Betty Ford Center, the White House, or another
associated organization without an award-source attribution.

## The 16 entries missing both identity and map location

These are the only entries that require both an identity decision and a coordinate decision.  They are all positions 2+
in `award_extra_affiliations`; their primary award rows may have complete affiliation data.

| Award record | Position | Recipient | Affiliation | City, country |
|---|---:|---|---|---|
| `breakthrough-000127` | 2 | Stuart H. Orkin | Dana-Farber Cancer Institute | Boston, United States |
| `lasker_awards-000294` | 2 | David J. Mahoney | Eleanor Naylor Dana Charitable Trust | New York, United States |
| `breakthrough-000129` | 2 | Frank Merle | Institut des Hautes Études Scientifiques | Bures-sur-Yvette, France |
| `breakthrough-000050` | 2 | Ian Agol | Institute for Advanced Study | Princeton, United States |
| `fields-000017` | 2 | Ngô Bao Châu | Institute for Advanced Study | Princeton, United States |
| `breakthrough-000031` | 2 | Saul Perlmutter | Lawrence Berkeley National Laboratory | Berkeley, United States |
| `breakthrough-000034` | 3 | Jennifer A. Doudna | Lawrence Berkeley National Laboratory | Berkeley, United States |
| `breakthrough-000015` | 2 | Eric S. Lander | Massachusetts Institute of Technology | Cambridge, United States |
| `breakthrough-000019` | 2 | Robert A. Weinberg | Massachusetts Institute of Technology | Cambridge, United States |
| `japan_prize-000101` | 2 | Robert A. Weinberg | Massachusetts Institute of Technology | Cambridge, United States |
| `breakthrough-000126` | 3 | Rosa Rademakers | Mayo Clinic | Jacksonville, United States |
| `breakthrough-000096` | 2 | Jun Ye | National Institute of Standards and Technology | Boulder, United States |
| `breakthrough-000139` | 2 | Adam G. Riess | Space Telescope Science Institute | Baltimore, United States |
| `breakthrough-000125` | 2 | Katherine A. High | University of Pennsylvania | Philadelphia, United States |
| `japan_prize-000102` | 2 | Katalin Karikó | University of Pennsylvania | Philadelphia, United States |
| `japan_prize-000002` | 2 | Ephraim Katchalski-Katzir | Weizmann Institute of Science | Rehovot, Israel |

Repeated names in this list must be resolved per entry only after checking that the row names the same parent institution.
The existing QID on a similarly named award row is evidence to review, not permission to copy it.

## Repair order

1. Preserve blank names where the award source does not identify an institution.  Do not replace them with `Freelance`,
   a role, a later employer, or a guessed institution.
2. For the 16 entries above, verify the parent institution and write its QID only when exact.  Resolve coordinates only
   after that identity check.
3. For the other 50 named, QID-bearing but unmapped entries, validate coordinates with
   `scripts/lookup_coordinates.py` and `scripts/reverse_nominatim.py` before a guarded blank-only update.
4. For the 53 mapped, QID-less entries, investigate the institution identity.  Leave the QID blank if no exact parent
   institution can be verified; the existing coordinates remain useful.

Every update must follow `AGENTS.md`: research before the transaction, back up the database, update only blank cells by
exact `award_record_id` and current-value guards, then read back the result and run `PRAGMA integrity_check`.

## Re-measurement query

Run from `datasets/`:

```sql
WITH affiliation_entries AS (
    SELECT award_record_id, affiliation_name, affiliation_coordinates, affiliation_wikidata_qid
    FROM awards WHERE TRIM(COALESCE(affiliation_name, '')) <> ''
    UNION ALL
    SELECT award_record_id, affiliation_name, affiliation_coordinates, affiliation_wikidata_qid
    FROM award_extra_affiliations WHERE TRIM(affiliation_name) <> ''
)
SELECT
    CASE WHEN TRIM(COALESCE(affiliation_wikidata_qid, '')) = '' THEN 'blank QID' ELSE 'has QID' END AS qid_status,
    CASE WHEN TRIM(COALESCE(affiliation_coordinates, '')) = '' THEN 'blank coordinates' ELSE 'has coordinates' END AS coordinate_status,
    COUNT(*) AS entries
FROM affiliation_entries
GROUP BY qid_status, coordinate_status
ORDER BY qid_status, coordinate_status;
```
