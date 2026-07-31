# Data gaps and quality census — 20260726

## Goals

Establish, with measured numbers rather than impressions, what data in `awards.sqlite3` is missing, malformed, or
structurally unable to hold the truth — so that remediation can be prioritised and specified separately. This document
**defines** gaps; it prescribes no fixes and changes no code.

A second goal is to separate a *gap* from a *legitimately blank cell*. `AGENTS.md` requires blank over guessed, so raw
blank counts systematically overstate the problem. Every count below is classified.

## Background

`awards.sqlite3` holds 3,091 award records across 14 prize families (3,047 Individual, 44 Organization), in one
`awards` table of 32 columns, plus `affiliations` (304 rows of institution metadata keyed by Wikidata QID) and
`award_ranking` (one row per prize family). The database is the sole source of truth; there is no rebuild path from
the archived CSVs.

`website/build.py` reads all three tables and renders 8,278 pages. Its quality ceiling is the data's: `plan_places()`
(`website/build.py:758-847`) derives every country and institution page from these columns, and `map_payload()`
(`website/build.py:482-558`) derives the atlas from the two coordinate columns. Where a field is blank the page is
silently thinner; where a field is malformed the page is silently wrong.

Two prior findings motivated this census. `docs/specs/datasets-site-roadmap-todo-20260726.md` §4 asserts gaps that this
document partly corrects (see Assumption 3 and the census note on birth data). Separately, several award records were
observed to list more than one institution — the case this schema cannot currently represent, described under
[Multiple affiliations](#multiple-affiliations-per-award-record).

Measurements were taken against `awards.sqlite3` on 2026-07-26. Every figure is reproducible with the queries in
[Re-measuring](#re-measuring).

## Assumptions

1. **Load-bearing.** `AGENTS.md` "validation rules" define correctness. A cell that those rules require to be blank is
   not a gap, however empty it looks.
2. **Load-bearing.** Blank means unknown, never zero and never false. The rule "leave a cell blank when unsure, do not
   guess or infer" is already honoured in the data, so a blank is evidence of an unmet research task, not of an error.
3. **Load-bearing.** Organizations legitimately carry no birth, sex, or death data. All 44 blanks in `birth_date`,
   `birth_country`, `birth_coordinates`, and `sex` are exactly the 44 Organization rows, and no Organization row
   carries any of that data. The roadmap's claim that "birth coordinates and sex are each missing for 44 records"
   describes correct data, not a gap.
4. **Load-bearing.** The established multi-value convention in this schema is a semicolon-separated list. Both
   `citizenship_countries` (460 records) and `affiliation_coordinates` (4 records) already use it, and
   `parse_map_points()` (`website/build.py:449-471`) already parses it with `multiple=True`.
5. Laureate identity is `laureate_wikidata_qid`, which is populated on all 3,091 records. Institution identity is
   `affiliation_wikidata_qid`, which is not.
6. Counts drift as enrichment continues. Each figure below is a dated measurement, not a constant.
7. This document defines gaps only. Each remediation — including the schema change in
   [Multiple affiliations](#multiple-affiliations-per-award-record) — requires its own spec before any code or data
   is touched.

## Scope

Zero code files and zero lines of code. One new document. Three follow-on specs are implied but not written here:
affiliation identity and cleanup, multi-value affiliation migration, and citizenship canonicalisation.

---

## Census of all 32 columns

`blank` counts empty or whitespace-only cells across all 3,091 records. `expected` is the portion that `AGENTS.md`
requires or permits to be blank. `gap` is the remainder — the research backlog.

| Column | Blank | Expected | Gap | Note |
|---|---:|---:|---:|---|
| `award_record_id` | 0 | — | 0 | Primary key |
| `year` | 0 | — | 0 | |
| `category` | 655 | 655 | 0 | Five prize families award no categories; each is 100% blank, which is the rule working |
| `prize` / `prize_name` | 0 | — | 0 | |
| `award_wikidata_qid` | 0 | — | 0 | |
| `motivation` | 0 | — | 0 | Complete on every record |
| `prize_share` | 387 | 387 | 0 | Not published by every family; MUST NOT be inferred |
| `source_laureate_id` | 1,562 | 1,562 | 0 | Only where the source exposes a stable ID |
| `laureate_wikidata_qid` | 0 | — | 0 | Complete; the identity spine of the dataset |
| `laureate_type` | 0 | — | 0 | |
| `full_name` | 0 | — | 0 | |
| `birth_date` | 44 | 44 | 0 | All Organizations |
| `birth_year` | 1,003 | 1,003 | 0 | Optional where `birth_date` is complete; 959 such rows, 44 Organizations. **No individual lacks both** |
| `birth_city` | 92 | 44 | **48** | 48 individuals with no recorded birth city |
| `birth_country` | 44 | 44 | 0 | |
| `birth_coordinates` | 44 | 44 | 0 | Complete for all 3,047 individuals |
| `citizenship_countries` | 35 | 35 | 0 | Organizations; see [Citizenship](#citizenship-ordering) for the real defect |
| `sex` | 44 | 44 | 0 | |
| `affiliation_name` | 326 | 33 | **293** | 293 individuals with no institution recorded |
| `affiliation_sub_name` | 2,975 | 2,975 | 0 | Department-level detail, recorded only where it disambiguates |
| `affiliation_city` | 561 | 322 | **239** | Name present, city absent |
| `affiliation_country` | 985 | 322 | **663** | Name present, country absent — the largest affiliation gap |
| `affiliation_coordinates` | 1,639 | 326 | **1,313** | Name present, coordinates absent — 47% of affiliated records |
| `affiliation_wikidata_qid` | 1,390 | 326 | **1,064** | Name present, no institution identity |
| `death_date` | 1,417 | 1,417 | 0 | Blank means living |
| `death_city` | 1,533 | 1,416 | **117** | Died, but place unrecorded |
| `death_country` | 1,526 | 1,416 | **110** | Died, but country unrecorded |
| `field_language` | 2,465 | 2,465 | 0 | Source-specific; supplied only by Nobel (562) and Economics (64) |
| `biographical_note` | 2,749 | 2,749 | 0 | Preserved only where a source supplied one — Crafoord 81/82, Gairdner 181/387, Breakthrough 80/148. MUST NOT be generated |
| `remarks` | 3,088 | 3,088 | 0 | Free-text exception log |
| `high_school_subject` | 0 | — | 0 | Complete; CHECK-constrained to 10 values |

**Blank-cell research backlog: 3,847 cells across 8 columns.** Everything else that reads as empty is empty by rule.

This total counts *absent* data only. It excludes every malformed and structural defect below — ~45 bad affiliation
strings, 49 records the schema cannot represent, 315 records with non-canonical citizenship order, 6 institutions
with conflicting coordinates, and 1 cross-field contradiction. Those are the defects a blank-cell count cannot see,
and several of them are the ones that make a page actively wrong rather than merely thin.

### Cross-field contradictions

Blank-only counting hides cells that are populated but mutually impossible. One such check found one record:

- `nobel-000551` (Carlo Rubbia) has a blank `death_date` with `death_city` = Geneva and `death_country` =
  Switzerland. Under `AGENTS.md` a blank death date means living, so the death place contradicts it. He is living;
  the death place is the error.

This is one instance of a class no query above would surface. A remediation SHOULD add a standing consistency check
alongside `scripts/check_coordinates.sql` rather than treating it as a one-off correction.

The single most striking result is that birth data for individuals is effectively complete — 3,047 of 3,047 have
coordinates — while institution data is missing on between 8% and 47% of records depending on the field. The dataset
knows where laureates came from far better than it knows where they worked.

---

## Affiliation identity

609 distinct name strings carry no QID, against 942 distinct names and 303 distinct QIDs overall. Two distinct
failures hide in that ratio.

**Name variants collapse onto one QID.** Where a QID exists it is often reached by several spellings:

| QID | Variants | Strings |
|---|---:|---|
| `Q189022` | 4 | Imperial College London · Imperial College of Science and Technology · Imperial College · Imperial College of Science |
| `Q280413` | 3 | Centre National de la Recherche Scientifique · French National Centre for Scientific Research (CNRS) · CNRS (VERIMAG) |
| `Q217365` | 3 | Bell Labs · Bell Telephone Laboratories · Bell Laboratories |
| `Q878218` | 2 | Max Planck Institute of Biochemistry · Max-Planck-Institut für Biochemie |

These are benign once the QID is present — the QID is the join key and the variants are cosmetic. They matter only
for the 609 unresolved names, where the string *is* the key and every variant fragments the count.

**Some strings are not institution names at all.** Confirmed malformed values:

- `breakthrough-000031`, `breakthrough-000138`, `breakthrough-000139` (Perlmutter, Schmidt, Riess) share the identical
  string `University of California, Berkeley and Lawrence Berkeley National Laboratory; Australian National
  University;Johns Hopkins University and Space Telescope Science Institute` — the union of all three laureates'
  institutions written onto each of them, with a missing space after the second semicolon. No record here is correct.
- `breakthrough-000080` holds the prose sentence `The EHT Collaboration consists of 13 stakeholder institutes:; the
  Academia Sinica Institute of Astronomy and Astrophysics; …` — a caption, not a name.
- `breakthrough-000002` holds `California Institute of Technology, Pasadena, CA Currently at KITP and UCSB, Santa
  Barbara` — name, city, state, and a career update in one cell. 18 records fold a country into the name this way
  (`…, USA`, `…, UK`), which `affiliation_country` already has a column for.
- `Freelance` appears on 19 records. It is not an institution and `build.py` already blocklists it
  (`AFFILIATION_BLOCKLIST`, `website/build.py:82`), which is a workaround at the presentation layer for a data
  problem. `Syndicated Columnist` (`lasker_awards-000224`) is the same class of value and is *not* blocklisted, so it
  currently has its own institution page.
- 4 names exceed 120 characters; 1 begins in lower case.

---

## Affiliation coordinates

1,313 records name an institution with no coordinates — the atlas therefore plots under half of the affiliated
records while presenting itself as complete. Of the coordinates that do exist, format discipline holds: all conform to
`longitude,latitude` at four decimal places, and none fail the range check in `parse_map_points()`.

Two consistency defects are measurable:

- **Six institution names carry two different coordinate pairs** across records — Yale, Cambridge, Johns Hopkins,
  Harvard, Cornell, and the Institute of Genetics and Molecular and Cellular Biology. One of each pair is wrong, or
  the name covers two campuses that the data does not distinguish.
- **`Q13371`-class collisions.** `0.1132,52.2054` is shared by two QIDs under the names "University of Cambridge" and
  "Cambridge University" — the same place, two identities, which will double-count on any institution ranking.

---

## Citizenship ordering

Citizenship is the healthiest of the four problem areas and the one whose defect is most easily missed. There are no
blanks among individuals, no historic country names, no commas or slashes, and a consistent `; ` delimiter. 460
records carry more than one country, across 199 distinct strings.

The defect is that the list is **unordered in principle but stored as an ordered string**, so the same fact appears in
two forms:

```
"United Kingdom; United States"    22 records
"United States; United Kingdom"    12 records     ← same fact
"Germany; United States"           22 records
"United States; Germany"           10 records     ← same fact
```

Of 166 two-country strings, **40 canonical pairs are stored in both orders, affecting 315 records**.

**No count is wrong because of this, but the inconsistency is visible to readers.** `explorer_payload()` splits the
field on `;` and collects country indices into a set (`website/build.py:411-413`), so the explorer's citizenship chart
is order-insensitive and no page groups by the raw string. However `FACT_FIELDS` (`website/build.py:96`) renders the
raw string verbatim in the facts panel of every winner page, so the same laureate can disagree with himself:

```
Oliver Smithies, 5 award records
  Gairdner 1990 · Gairdner 1993 · Lasker 2001 · Nobel 2007   "United States; United Kingdom"
  Wolf 2002/2003                                             "United Kingdom; United States"
```

His Wolf Prize page states his citizenship in a different order from his Nobel page. Nothing is miscounted; the site
simply looks careless on exactly the kind of detail this project claims to get right. The defect also misleads any
`GROUP BY citizenship_countries` written against the database directly — which is how this census and most ad-hoc
analysis reach the data.

A remediation MUST choose and document a canonical order (alphabetical is the obvious candidate) and SHOULD state
whether order ever carries meaning, such as country of birth first. This document does not decide that. Given that
nothing downstream is broken, this ranks below the affiliation work.

---

## Multiple affiliations per award record

### The finding

A laureate is frequently recognised while holding two or more posts, and the awarding body records all of them. The
schema has one slot per field, so the surplus is either lost or crammed into the name string. 49 records currently
pack several institutions into `affiliation_name` with a semicolon:

```
breakthrough-000011  Bert Vogelstein   Howard Hughes Medical Institute; Johns Hopkins University
breakthrough-000015  Eric S. Lander    Massachusetts Institute of Technology; Broad Institute
breakthrough-000020  Shinya Yamanaka   Kyoto University; J. David Gladstone Institutes; UCSF
breakthrough-000034  Jennifer Doudna   UC Berkeley; Howard Hughes Medical Institute; LBNL
```

### Why it is worse than it looks

`plan_places()` groups institutions by the **raw `affiliation_name` string** (`website/build.py:783-784` and
`802-804`), not by QID. A packed string therefore does not collapse onto its first institution — it becomes a
*separate institution in its own right*, with its own slug, its own page, and its own laureate count. These pages are
live today:

```
/affiliations/howard-hughes-medical-institute-johns-hopkins-university/
/affiliations/massachusetts-institute-of-technology-broad-institute/
/affiliations/university-of-california-berkeley-and-lawrence-berkeley-national-labora-43b500cb/
```

937 institution pages are generated from 942 distinct name strings, of which 33 have slugs encoding more than one
institution. The consequence is that a real institution's laureates are **split across phantom pages**.

Jennifer Doudna is the clearest verified case. She holds five award records naming four different institution
strings:

```
breakthrough-000034   "UC Berkeley; HHMI; LBNL"        Q168756  ─► phantom page
gairdner…-000336      "University of California, Berkeley"  Q168756  ─► Berkeley page
japan_prize-000090    "University of California, Berkeley"  Q168756  ─► Berkeley page
wolf_prize-000343     "University of California, Berkeley"  Q168756  ─► Berkeley page
nobel-000952          "University of California"       Q184478  ─► a third page, the UC system
```

Her Breakthrough Prize is attributed to
`/affiliations/university-of-california-berkeley-howard-hughes-medical-institute-lawre-432a736f/` — an institution
that does not exist. **The Howard Hughes Medical Institute page names her nowhere**, despite HHMI appearing on that
record. Her Nobel lands on a third page again, because that record says "University of California" and carries
`Q184478`, the university system rather than the Berkeley campus.

Only **5 of the 49 packed records carry a QID at all**, and all 5 resolve to `Q168756` — the first institution in the
string. The other 44 have no institution identity whatsoever. So the QID column does not merely under-report; where
it is populated on a packed string it asserts one institution for a record describing three, and any metadata
attached to it — logo, description, application link — is then rendered on a page describing all three.
`plan_places()` guards only the reverse case, raising `conflicting affiliation metadata` when one slug carries
several profiled QIDs (`website/build.py:834-835`).

The map already concedes the problem. When a record has more than one coordinate pair, `map_payload()` labels the
point `"Multiple recorded institutions"` (`website/build.py:519-521`) because it cannot name them.

```
TODAY                          one string → one phantom institution, keyed by raw name

  affiliation_name  "UC Berkeley; HHMI; LBNL"  ──►  /affiliations/university-of-california-
  affiliation_qid   "Q168756"   (Berkeley only)     berkeley-howard-hughes-medical-
  affiliation_coord "-122.26,37.87"                 institute-lawre-432a736f/

                                                    Berkeley page:  omits this award
                                                    HHMI page:      omits Doudna entirely
                                                    LBNL page:      omits Doudna entirely
```

### Candidate direction — decided by the owner, settled by a later spec

This document does not choose the fix (Assumption 7). It records the direction the project owner selected on
2026-07-26 so the follow-on spec starts from a stated preference rather than re-opening it: **semicolon-separated
parallel lists**, extending the convention `affiliation_coordinates` and `citizenship_countries` already follow
(Assumption 4). No new table, no migration of `affiliations`, and `parse_map_points()` already reads this shape. The
alternative considered was a join table.

The migration spec MUST re-test this choice against the invariant below before implementing it.

```
TARGET                                       six parallel lists, one index per institution

  affiliation_name          "Harvard University; Institute for Advanced Study"
  affiliation_sub_name      "; "
  affiliation_city          "Cambridge; Princeton"
  affiliation_country       "United States; United States"
  affiliation_coordinates   "-71.1167,42.3770;-74.6672,40.3319"
  affiliation_wikidata_qid  "Q13371; Q1140681"
                              [0]              [1]
```

**The invariant this creates, which nothing currently enforces:** for any record, every non-blank affiliation column
MUST contain the same number of semicolon-separated segments, and segment *i* of each column MUST describe the same
institution. A blank segment is a permitted unknown and MUST be preserved positionally, as `affiliation_sub_name`
shows above — dropping it silently re-indexes every column after it.

Today that invariant already fails: the 4 records with two coordinate pairs (`fields-000004`, `fields-000017`,
`fields-000020`, `fields-000034`) have two coordinates, one prose name, and zero QIDs.

The cost of this model is that the invariant lives in convention and in whatever validation is written to guard it,
not in the schema. A join table would enforce it structurally at the price of a larger migration through
`read_database()` (`website/build.py:581-641`) and `plan_places()`. A future reviewer reading this section is reading
a considered preference, not an oversight — and not yet a commitment.

A second cost, specific to this dataset: `plan_places()` keys institutions by the raw name string, so splitting the
packed names is not sufficient on its own. Whatever the migration does, the grouping key MUST move to the QID, or the
phantom pages simply become phantom *segments*.

Any migration spec MUST state how the 49 packed strings are split, how a QID is resolved per segment, and what the
build does when segment counts disagree — fail the build, as `parse_map_points()` does today, or degrade.

---

## Institution metadata

`affiliations` holds 304 rows against 303 distinct QIDs in use — one row is unreferenced.

| Field | Blank | Note |
|---|---:|---|
| `logo_url` | 171 | 56% of institutions render without a logo |
| `description` | 4 | Effectively complete |
| `application_url` | 1 | Effectively complete |

This table will need one row per newly resolved QID as the 1,064 unresolved records are closed.

---

## Priority

Ranked by how wrong the published site is, not by record count. Absent data makes a page thin; malformed data makes
it false, so the small defects outrank the large gaps.

1. **Packed affiliation names** — 49 records, 33 live phantom institution pages. The only defect on this list that
   publishes statements that are simply untrue: institutions that do not exist, and real institutions whose pages
   omit laureates they hold. Fixing this requires the multi-value model, so the two are one piece of work.
2. **Malformed affiliation strings** — ~45 records: 19 `Freelance`, 1 `Syndicated Columnist` with a live page, 18
   folding a country into the name, and a handful of prose and merged strings. Actively wrong, and cheap to fix by
   hand.
3. **Affiliation identity** — 1,064 records. Blocks institution metadata, the map's affiliation layer, and country
   attribution. It is also the prerequisite for (1): per-segment QIDs cannot be resolved while single-value QIDs are
   themselves 38% incomplete, and the grouping key cannot move from name to QID until the QIDs exist.
4. **Affiliation coordinates** — 1,313 records. Largely falls out of (3); a resolved QID yields coordinates through
   `scripts/lookup_coordinates.py`.
5. **Citizenship canonicalisation** — 315 records. Mechanical once the order rule is chosen. No count is wrong, but
   the raw string is displayed, so laureates with several awards can contradict themselves across their own pages.
6. **Long tail** — 293 records with no affiliation at all, 48 birth cities, 117 death cities, 110 death countries,
   and the single Rubbia contradiction.

Note the ordering tension between (1) and (3): the phantom pages are the most visible damage, but the identity work
gates the clean fix. A remediation spec MAY choose to hand-correct the 49 packed records ahead of the broader
identity work to stop publishing phantom institutions sooner.

---

## Re-measuring

Every figure above is reproducible. The census pattern, for any column:

```sql
SELECT count(*) FROM awards WHERE trim(coalesce(<column>,'')) = '';
SELECT count(*) FROM awards WHERE trim(coalesce(<column>,'')) = '' AND laureate_type = 'Individual';
```

The affiliation gaps, which are conditional on a name being present:

```sql
SELECT count(*) FROM awards
WHERE trim(coalesce(affiliation_name,'')) <> ''
  AND trim(coalesce(affiliation_wikidata_qid,'')) = '';
```

Citizenship pairs stored in both orders:

```sql
WITH two AS (
  SELECT citizenship_countries v,
         trim(substr(citizenship_countries, 1, instr(citizenship_countries,';') - 1)) a,
         trim(substr(citizenship_countries, instr(citizenship_countries,';') + 1)) b,
         count(*) n
  FROM awards
  WHERE citizenship_countries LIKE '%;%'
    AND length(citizenship_countries) - length(replace(citizenship_countries,';','')) = 1
  GROUP BY 1
),
canon AS (SELECT CASE WHEN a < b THEN a||' | '||b ELSE b||' | '||a END k, v, n FROM two)
SELECT count(*) FROM (SELECT k FROM canon GROUP BY k HAVING count(DISTINCT v) > 1);
```

Records packing several institutions into one name:

```sql
SELECT award_record_id, full_name, affiliation_name FROM awards WHERE affiliation_name LIKE '%;%';
```

Cross-field contradiction — a death place recorded against a living laureate:

```sql
SELECT award_record_id, full_name, death_city, death_country FROM awards
WHERE trim(coalesce(death_date,'')) = ''
  AND (trim(coalesce(death_city,'')) <> '' OR trim(coalesce(death_country,'')) <> '');
```

Institution names carrying conflicting coordinates:

```sql
SELECT affiliation_name, count(DISTINCT affiliation_coordinates) n FROM awards
WHERE trim(coalesce(affiliation_coordinates,'')) <> ''
GROUP BY 1 HAVING n > 1;
```

Existing checks not duplicated here: `scripts/check_coordinates.sql` reports birth coordinates pointing at the wrong
place, and `PRAGMA integrity_check` proves file health but says nothing about correctness.
