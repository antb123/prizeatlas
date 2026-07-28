# Affiliation records — source of truth (20260728)

Reference, not a spec. It describes the affiliation data as it exists in `datasets/awards.sqlite3` today, states where each
value is allowed to come from, and gives agents the rules for entering and validating it. Nothing here proposes a change.

Design history lives in the specs and is not repeated: `datasets-affiliation-sub-name-20260725.md` (roll-up),
`datasets-award-affiliations-20260727.md` (second and later affiliations), `datasets-affiliation-metadata-20260726.md`
(institution profiles), `website-compact-affiliation-units-20260728.md` (ranking display).

## 1. What an affiliation record is

One affiliation = the institution a laureate was at **when the award was made**, recorded against one `award_record_id`.
It is not the laureate's career history, not their current employer, and not the institution that nominated them.

An award may carry several affiliations. They live in two disjoint stores, plus a third table holding institution-level
metadata that is shared across awards:

```
awards                              one row per laureate/award; the six flat affiliation_* columns are POSITION 1
  award_record_id (PK)
  affiliation_name … qid  ─────┐
                               ├──→  composed in read_database()  ──→  record.affiliations = (pos 1, pos 2, …)
award_extra_affiliations       │
  (award_record_id, position) ─┘     POSITIONS 2+ — same six columns, one row per extra affiliation
       │
       │ affiliation_wikidata_qid
       ▼
affiliations                        one profile per institution QID — logo, description, application URL
  affiliation_wikidata_qid (PK)     joined only on an exact nonblank QID; never by name, slug, or coordinates
```

**Position is a sort key, not a rank.** Position 1 living in the flat columns is storage, not a claim of primacy.
The stores are disjoint by construction: `CHECK (position >= 2)`. No affiliation fact is ever stored twice.

## 2. Where the values come from

In this order. Never skip to a later source when an earlier one answers the question.

| Rank | Source | Supplies |
|---|---|---|
| 1 | The award's own website (list in `AGENTS.md` per prize family) | `affiliation_name`, and `affiliation_city` / `affiliation_country` where the citation gives them |
| 2 | Wikidata, matched by QID | `affiliation_wikidata_qid`, and coordinates via `scripts/lookup_coordinates.py` |
| 3 | Nominatim, as the second opinion on a place | confirmation only — `scripts/lookup_nominatim.py`, `scripts/reverse_nominatim.py` |

The award site names the institution; Wikidata identifies it. A QID is written only after the institution has been matched
to that exact item — the same name is not proof.

**The QID identifies the ranked parent in `affiliation_name`, never the unit in `affiliation_sub_name`.** Every UC campus
row carries `Q184478` (the system) and every Harvard unit row carries `Q13371` (the university). Units have no QID column;
they are identified by their sub-name alone. A unit's own QID in this column is a defect — the profile join requires one
QID per parent page and the build raises `BuildFailure` on a page holding two.
Places are recorded under **today's** name, country, and location, even when the award is a century old.

Blank is a legitimate value everywhere. Leave a cell blank rather than guessing — unless the curator directs otherwise,
which they may do for any rule here (§6 rule 0).

## 3. Field reference

### 3.1 `awards` — the flat columns (position 1)

| Column | Type | Blank | Meaning |
|---|---|---|---|
| `affiliation_name` | TEXT | `''` | Canonical **parent** institution. What `/affiliations/` ranks on. One institution, one spelling. |
| `affiliation_sub_name` | TEXT NOT NULL DEFAULT `''` | `''` | The constituent unit as displayed — campus, school, institute, department, lab. Never ranked. See §4. |
| `affiliation_wikidata_qid` | TEXT (nullable) | `''` or SQL `NULL` | Wikidata item of the institution on this row. 750 rows hold `NULL`; `_text()` in `website/build.py` flattens it on read. |
| `affiliation_city` | TEXT | `''` | City alone, today's name. No `City, ST`. Describes the **unit**, not the parent — see §4.4. |
| `affiliation_country` | TEXT | `''` | Modern country. Single-valued: the `;` convention is retired for affiliations (it survives only in `citizenship_countries`). |
| `affiliation_coordinates` | TEXT | `''` | `longitude,latitude`, four decimals. Written only after the named place is verified by two sources. |

The six columns are wholly blank on 323 rows: that award has no position-1 affiliation. If it also has no extras row, it
has no recorded affiliation at all, and no affiliation section renders.

### 3.2 `award_extra_affiliations` — positions 2+

```sql
CREATE TABLE award_extra_affiliations (
    award_record_id          TEXT    NOT NULL REFERENCES awards(award_record_id),
    position                 INTEGER NOT NULL CHECK (position >= 2),
    affiliation_name         TEXT    NOT NULL DEFAULT '',
    affiliation_sub_name     TEXT    NOT NULL DEFAULT '',
    affiliation_city         TEXT    NOT NULL DEFAULT '',
    affiliation_country      TEXT    NOT NULL DEFAULT '',
    affiliation_coordinates  TEXT    NOT NULL DEFAULT '',
    affiliation_wikidata_qid TEXT    NOT NULL DEFAULT '',
    PRIMARY KEY (award_record_id, position)
) STRICT;
```

Same six columns, same rules, same meanings as §3.1. Differences that matter:

- Every column is `NOT NULL DEFAULT ''` — there is no `NULL` QID here, unlike the flat store.
- Full location is carried on every row. An institution's place is **never** resolved by joining on its name.
- The foreign key is documentation: `PRAGMA foreign_keys` is off. The loader refuses a TSV naming an unknown award, and
  that is the **only** orphan check — no validator check covers it, so a row inserted any other way stays silent. 0 today.
- **The normalizer never sees this table.** It reads and writes `awards` only, so `AFFILIATIONS` does not apply here:
  canonical parent names and sub-names must be typed correctly **in the TSV by hand**. Three rows currently store
  `Harvard Medical School` as a standalone parent (TSV lines 7, 65, 79) where the flat store rolls it into
  `Harvard University` — the website ranks and routes those separately, which is the bug this warning exists to prevent.
- The table is not hand-edited. `datasets/award_extra_affiliations.tsv` is its source of truth and every load replaces the table's whole contents from it.
- **A load destroys anything written straight to the table.** The replace is total: a value in the table but not in the TSV
  is gone, silently. Someone had hand-written two, and a load dropped them. Before loading, diff the table against the file:
  `ATTACH` the pre-load backup and select rows where the old value is nonblank and the new one is blank.

Positions count from 2 upward per award, in TSV file order. An award whose flat columns are blank still starts its extras
at 2; the gap at position 1 is correct and means "no first affiliation recorded".

### 3.3 `affiliations` — institution profile, keyed by QID

```sql
CREATE TABLE affiliations (
    affiliation_wikidata_qid TEXT PRIMARY KEY,
    logo_url                 TEXT NOT NULL DEFAULT '',
    description              TEXT NOT NULL DEFAULT '',
    application_url          TEXT NOT NULL DEFAULT ''
) STRICT;
```

One row per institution, not per award. `application_url` was added after `datasets-affiliation-metadata-20260726.md`
was written; that spec still describes three columns.

- Attaches to an affiliation page only when the page's records carry exactly one distinct nonblank QID and that QID has a profile.
- One page carrying two different nonblank QIDs where either has a profile is a `BuildFailure`, not a guess.
- **Neither URL is validated by anything.** `datasets-affiliation-metadata-20260726.md` specified an HTTPS/host/credentials
  gate for `logo_url`; it was never implemented. `validate_official_url` exists in `website/build.py` but is applied only to
  `award_ranking.url`. Profile validation checks QID format and duplicates, nothing else, and `application_url` is rendered
  straight into an `href`. 80 rows hold plain-HTTP application URLs today. Treat both columns as unguarded: check the URL
  by hand before inserting it.
- A QID is eligible only after every live award row carrying it has been confirmed to be the same real institution. A QID
  spread across two institutions (the `umbrella-qid` check) must be fixed in the award data first.

## 4. Sub-affiliations

### 4.1 The model

```
affiliation_name      "Harvard University"       canonical parent — ranked
affiliation_sub_name  "Harvard Medical School"   the unit — displayed beneath the parent, never ranked
```

A unit rolls up only when it is **legally part of** the named parent: a campus, school, college, faculty, department,
laboratory, or institute. Legally independent institutions stay standalone however closely they are tied — teaching
hospitals (Massachusetts General, Brigham and Women's, Mayo Clinic, St. Jude), Baylor College of Medicine, London School
of Economics, Albert Einstein College of Medicine. The full "not merged" list with its reasons is the comment block above
`AFFILIATIONS` in `scripts/normalize_affiliations.py`; that comment, not this file, is the operative copy.

Three shapes of unit are in use today, and they behave identically:

| Shape | Parent | Sub-name |
|---|---|---|
| Campus of a system | `University of California` | `University of California, Berkeley` |
| School or faculty | `Johns Hopkins University` | `School of Medicine` |
| Institute of a society | `Max Planck Society` | `Max Planck Institute of Biochemistry` |

A university-owned hospital or clinic is recorded as a unit of its university (`Shanghai Jiao Tong University` ←
`Ruijin Hospital, School of Medicine`). An independent hospital is its own institution with a blank sub-name.

### 4.2 Deciding whether something is a unit

Apply these in order and stop at the first that answers. Record the answer and its reason in the `NOT MERGED` comment
block or the `AFFILIATIONS` entry — the judgement is worth more than the mapping line it produces.

| # | Test | Answer | Weight |
|---|---|---|---|
| 1 | **One legal entity?** Can it hold property, sue, be sued, and confer its own degrees in its own name? | Same legal person as the parent → **unit** | Decisive |
| 2 | **One board of governance?** Does a separate board hold final authority over appointments, property, and finance — or is the parent's board sovereign, with only an advisory board of overseers/visitors below it? | Parent's board is sovereign → **unit**. Its own sovereign board → **independent** | Decisive |
| 3 | **One budget?** | See below | **Weak — do not decide on this** |
| 4 | **Wikidata.** `P749` parent organization or `P361` part of pointing at the parent supports unit; an item that is `instance of` university/research institute with no `P749` supports independent. | Corroborating | Cross-check only |
| 5 | **Ranking override.** Tests 1–2 say unit, but the world universally ranks it standalone. | Record it **standalone** anyway, with the reason written down | Display decision |

**Budget is the weak test and it will mislead you.** Devolved budgeting is normal inside a single university, so a unit
having "its own budget" proves nothing. Both of these have separately managed finances and both are correctly units here:

- Harvard runs *every tub on its own bottom* — Harvard Medical School manages its own finances, and one Harvard
  Corporation governs it. Test 2 says unit; test 3 would have said independent and been wrong.
- Each University of California campus has its own chancellor and budget, under one Board of Regents for the whole
  system. Test 2 says unit; test 3 would have split the system into ten institutions.

Use budget only as a tiebreaker when tests 1 and 2 genuinely cannot be established.

Worked against decisions already in the data: Harvard Medical School (one Harvard Corporation) and UC Berkeley (one Board
of Regents) are units; Massachusetts General Hospital and Baylor College of Medicine have their own boards and stay
standalone. LSE is the case that shows why test 2 beats "legally part of" — a constituent college of the University of
London, so a part-of reading makes it a unit, but its own Court of Governors and test 5 both keep it standalone.

**Two parents means neither.** JILA is a joint NIST / University of Colorado institute with no single sovereign board, so
it cannot be a unit of either — which is why `Q1586184` sits in §9 unresolved. Where a row's real employer is knowable,
record that; where it is not, keep the institute standalone rather than assigning it to one parent.

### 4.3 The mapping is written, never derived

`scripts/normalize_affiliations.py` holds one hand-reviewed table, `AFFILIATIONS: dict[str, tuple[parent, sub_name]]`.
An empty sub-name means a pure spelling alias; a nonempty one means a roll-up. No text rule may replace it — stripping a
trailing comma clause would merge `University of California, Berkeley` into `University of California`, and matching on
`"School of"` would swallow government bodies and independent colleges.

Two invariants hold the design up:

- **No target is ever a source.** Enforced at import; a violating edit raises `NormalizeFailure` before any write.
- **Sub-names use the unit's current canonical name, not the name as recorded.** Cornell's medical college was renamed in
  1998 and UMass's in 2021; bucketing on the recorded spelling would split one unit in two, which is the fragmentation
  the table exists to remove.

How fully a sub-name is written varies by parent — `Harvard Medical School` reads correctly in full, `School of Medicine`
reads correctly under `Johns Hopkins University`. That inconsistency is deliberate and judged per entry.

### 4.4 Geo columns describe the unit — the sharpest edge here

Roll-up rewrites the name and deliberately leaves `affiliation_city`, `affiliation_country`, and `affiliation_coordinates`
describing the unit. One parent therefore legitimately holds several cities:

```
Harvard University  ← Harvard Medical School         Boston      ┐ 220 miles apart, both correct:
Harvard University  ← (no unit)                      Cambridge   ┘ the columns answer "where was this laureate"
Cornell University  ← Weill Cornell Medical College  New York
Cornell University  ← (no unit)                      Ithaca
```

`SELECT DISTINCT affiliation_name, affiliation_city` will show Harvard in two cities. **Do not "fix" it.** Any per-institution
page or map keyed on the parent name must choose a representative location explicitly.

### 4.5 How units reach the website

Ranking counts **distinct laureates per parent**, never award rows, and is never re-derived by summing units — a laureate
recorded under both a school and the university proper would be counted twice. Sub-unit counts therefore need not sum to
the parent count. The blank bucket is suppressed: a parent with no recorded unit renders exactly as it always did. The
global ranking shows the top three units and puts the rest behind a native `+ N more` disclosure; the institution detail
page remains the complete drill-in.

In JSON-LD the `Organization` name stays the parent and the unit becomes a nested `department` Organization.

## 5. Ownership — who writes what

| Column / table | Written by | Notes |
|---|---|---|
| `awards.affiliation_name`, `affiliation_sub_name` | `scripts/normalize_affiliations.py --apply` only | Derived and owned; the write is unguarded, which is what makes re-running a no-op. |
| `awards.affiliation_city/country/coordinates/qid` | hand SQL by `award_record_id`, after two-source verification | Fill blanks only; never overwrite a curated value. No script does this — see §6.1. |
| `award_extra_affiliations` (all) | `scripts/load_extra_affiliations.py` from `award_extra_affiliations.tsv` | Full replace on every run. Edit the TSV, reload. |
| `affiliations` (all) | curated data work; `scripts/enrich_affiliations.py` for logo/description | Insert only after the QID identity audit. **`scripts/enrich_application_urls.py` is unsafe — do not run it, see §10.** |

Two scripts are commonly mistaken for QID fillers and are not:

- `scripts/enrich.py` never touches affiliation fields at all — its write set is birth, death, sex, and type.
- `scripts/enrich_affiliations.py` reads the QIDs already present on award rows and fills the **`affiliations` profile table**
  from Wikidata (description, P154 logo, P17 country, P571 inception). It never writes `awards.affiliation_wikidata_qid`.

### 5.1 Filling a missing QID on an award row — the only path

425 named rows carry no QID (750 hold SQL `NULL`, 2 hold `''`, the rest are unnamed rows). Nothing automates this; it is
hand work, one `award_record_id` at a time:

```
1. resolve   uv run scripts/lookup_coordinates.py "<institution>" --country "<country>"
             → properties.wikidata_id is the QID; properties.source is the URL to keep in the handoff
             lookup_coordinates.py:211 appends ", <country>" to every non-QID query. That is deliberate — it stops a
             bare name silently matching the wrong place, and AGENTS.md expects roughly three quarters of bare names
             to fail. Failing is the tool working. But the failure does not always list candidates to choose from:
             when the search returns nothing, the message names none. Then search wbsearchentities on the bare name,
             pick the item by its label and description, and rerun with the exact QID — the QID path skips the suffix.
2. confirm   the item is the institution ON THE ROW — not its parent body, not its successor, not a same-named other place
3. write     UPDATE awards SET affiliation_wikidata_qid = 'Q…'
              WHERE award_record_id = '…' AND COALESCE(affiliation_wikidata_qid, '') = '';
             The COALESCE guard is mandatory: the column is nullable, so `= ''` alone silently matches nothing.
4. check     the QID must not already sit on a different institution (§7, umbrella-qid) or add a name variant (§7, query A)
```

Never bulk-fill by name match. A QID borrowed from a same-named row is the defect this whole section exists to prevent.

`datasets/awards_affiliations.tsv` (3091 rows) is a **working set**, not a store: no script reads it and nothing is
generated from it. Never treat it as authoritative and never load from it.

## 6. Rules for agents — entering data

**0. The person directing the work overrides every rule in this file.** These rules are the default for an agent working
unattended; they exist to stop it inventing data, not to overrule the curator. When the curator supplies a value, names a
source, sets the scope, or tells you to pick, that instruction wins — including over "leave it blank when unsure" and the
two-source requirement. Three things still hold when a rule is overridden: back up first, record in the handoff that the
value was directed rather than sourced, and say once if the instruction contradicts data already in the database. Say it
once. A curator who repeats or confirms an instruction has decided, and the decision is theirs to make.

1. **Back up first, always.** `cp awards.sqlite3 awards.sqlite3.$(date +%Y%m%d-%H%M%S).<what>.bak` — there is no rebuild path.
2. **Finish research before opening a transaction.** Keep transactions short.
3. **Select by `award_record_id`, never by name.** Guard every update against the cell's current blank value.
4. **Fill blanks only.** Never overwrite a curated value; if a value looks wrong, flag it, do not silently replace it.
5. **Leave it blank when unsure.** Blank is a recorded fact. A guess is a defect that outlives the session.
6. **Name from the award site, identity from Wikidata, place confirmed by two sources.** Coordinates go in only after the
   named place is verified, as `longitude,latitude` to four decimals. A bare city name has only one practical resolver —
   Nominatim — so a city with no Wikidata item is single-source by nature: either resolve the city to an item first, or
   record it as directed under rule 0 and say so in the handoff. Never present one source as two.
7. **A second affiliation is never a hand INSERT.** Add the reviewed row to `award_extra_affiliations.tsv`, then run
   `uv run scripts/load_extra_affiliations.py --dry-run` and, if clean, without the flag. Only hand-reviewed rows go in.
   The normalizer does not reach this file: type the canonical parent and sub-name yourself, and check the name against
   `SELECT DISTINCT affiliation_name FROM awards` before saving.
8. **A new spelling or unit is never a hand UPDATE.** Decide unit vs. independent by §4.2 — governance, not budget — then
   add the entry to `AFFILIATIONS` in `scripts/normalize_affiliations.py` and run it. Check the disjointness invariant
   survives your edit: your target must not already be a key.
9. **Never borrow a QID, city, or coordinate from a same-named row.** That is exactly what split Berkeley 34/28 once already.
10. **Never invent a campus.** If the source says only `University of California`, the campus stays unrecorded.
11. **Do not use `;` in any affiliation column.** Positions replace it. It remains valid only in `citizenship_countries`.
12. **Record what the source said, at the time of the award.** Not the laureate's later or current post.
13. **A missing QID is filled by hand, per row, by the path in §5.1.** No script does it.
14. **Type the apostrophe the institution uses, and check both forms before adding a name.** `'` (U+0027) and `’` (U+2019)
    are different values under SQLite's BINARY collation, so `Children's` and `Children’s` are two institutions to every
    query, every ranking, and the `AFFILIATIONS` disjointness guard. Both forms are live in the data today.

## 7. Rules for agents — validating data

Run in this order after any affiliation write:

```
1. sqlite3 awards.sqlite3 "PRAGMA integrity_check;"          → must be exactly ok (file health only, says nothing about correctness)
2. uv run scripts/validate_awards.py                          → 9 checks; bare invocation runs all of them, there is no --all
3. uv run scripts/normalize_affiliations.py                   → dry run; read the report before ever passing --apply
4. uv run pytest tests/ ; uv run ruff check
5. uv run website/build.py --base-url https://example.org/awards/   → the build is the last gate; it fails on QID conflicts
```

`validate_awards.py` splits its checks into fatal invariants (non-zero exits 1) and counted backlogs. Use
`--check <name>` to run one and `--detail N` to print offending rows. Live counts at 20260728:

| Check | Fatal | Groups | What it means |
|---|---|---:|---|
| `coords-without-qid` | yes | 20 | Coordinates with nothing to source them from |
| `institution-facts-disagree` | yes | 76 | One institution recorded with two different cities, coordinates, or QIDs |
| `coords-shared-across-cities` | yes | 18 | One coordinate claimed by rows in different cities — one of them is wrong |
| `laureate-two-names` | yes | 0 | One laureate QID under two names — the build refuses this |
| `umbrella-qid` | no | 16 | A QID naming a parent body, not the place on the row |
| `sub-name-is-the-institution` | no | 16 | The sub-name holds the real institution while the name holds a parent — **mostly not defects**, read on |
| `city-with-state-suffix` | no | 0 | `City, ST` against the bare-city house style |
| `affiliation-without-qid` | no | 269 | Cannot be linked, logoed, or mapped |
| `missing-place` | no | 60 | No city or no country |

Three fatal checks currently fail. That is the inherited baseline, not a new break.

**Diff the group list, never the count.** Save `validate_awards.py --detail 200 > before.txt` and diff it after your write.
`--detail 0` prints counts with no groups, so it cannot answer the question this paragraph asks.
Counts hide two things: a group that disappears masks one you added, and an already-failing group that gains a second
conflict does not move the number at all.

**Blank counts as a value.** Every `COUNT(DISTINCT …)` here treats `''` as one, so filling *some* rows of an institution
and not the rest creates a group where there was none. Before writing, group the institution across both stores and see
whether your fill lands it on one value or two.

**`institution-facts-disagree` is fatal but overshoots.** It groups by parent name and fires on more than one distinct
city, coordinate, or QID — which §4.4 says is *correct* for a parent whose units sit in different cities. Harvard in Boston
and Cambridge is in its 111 groups by design. Read the group before treating it as a defect: differing cities across
different sub-names is the model working; differing cities on the *same* sub-name, or two QIDs on one parent, is a defect.

**Read `sub-name-is-the-institution` carefully before acting on it.** It is a containment test — `sub_name LIKE name || '%'
OR sub_name LIKE '%' || name || '%'` — so the campus naming rule trips it by design: 16 groups / 170 rows today, of which
152 rows are `University of California ← University of California, <campus>` and are exactly what §4.1 prescribes. The
genuine defects inside it are the ones where the sub-name restates the parent with nothing added:

| Parent | Sub-name | Rows |
|---|---|---:|
| `University College London` | `University College London` | 6 |
| `Google` | `Google DeepMind` | 6 |
| `Thomas J. Watson Research Center` | `IBM Thomas J. Watson Research Center` | 6 |

The check also misses the reverse direction — parent contains sub-name — which is the same defect written backwards:
`University of Colorado, JILA ← JILA` (3 rows) and `University of Toronto Ontario Cancer Institute ← Ontario Cancer
Institute` (2). In both, the parent name has swallowed its own unit and should be the bare institution.

`institution-facts-disagree` is the specific control on the two-store design — a position-2 affiliation typed with a
different city than the same institution's position-1 rows. It reads both stores through one CTE; any new affiliation SQL
must do the same or it will silently see half the data:

```sql
WITH affiliations AS (
    SELECT award_record_id, 1 AS position, affiliation_name, affiliation_sub_name, affiliation_city,
           affiliation_country, affiliation_coordinates, COALESCE(affiliation_wikidata_qid, '') AS affiliation_wikidata_qid
      FROM awards
    UNION ALL
    SELECT award_record_id, position, affiliation_name, affiliation_sub_name, affiliation_city,
           affiliation_country, affiliation_coordinates, affiliation_wikidata_qid
      FROM award_extra_affiliations
)
```

### 7.1 Identity checks the tooling does not do for you

`normalize_affiliations.py` matches on **exact strings**. It cannot see that two different spellings are the same
institution once they already carry the same QID, and it cannot see that one name has been given two QIDs. Both are
identity defects, and both need these queries — run them after any QID or name write.

**Query A — one QID, several names.** The `umbrella-qid` check reports this, but the query below is the one to work from
because it ranks by blast radius. 4 QIDs / 30 rows today:

```sql
SELECT affiliation_wikidata_qid,
       COUNT(DISTINCT affiliation_name) AS name_variants,
       COUNT(*)                         AS rows
FROM awards
WHERE affiliation_wikidata_qid <> ''
GROUP BY affiliation_wikidata_qid
HAVING COUNT(DISTINCT affiliation_name) > 1
ORDER BY rows DESC;
```

Two readings, and they need opposite fixes: either the names are **spellings of one institution** (add an `AFFILIATIONS`
alias) or the QID is an **umbrella wrongly applied to distinct places** (fix the rows, never the mapping). §9 lists the
three currently open cases.

**Query B — one name, several QIDs.** The inverse of `umbrella-qid`, and **no check covers it**. 1 group today
(`University of Pittsburgh`: `Q235034` on 2 rows, `Q7896139` — the School of Medicine — on 2 more):

```sql
SELECT affiliation_name,
       COUNT(DISTINCT affiliation_wikidata_qid) AS qids,
       COUNT(*)                                 AS rows
FROM awards
WHERE affiliation_wikidata_qid <> '' AND affiliation_name <> ''
GROUP BY affiliation_name
HAVING COUNT(DISTINCT affiliation_wikidata_qid) > 1
ORDER BY rows DESC;
```

This is always a defect. `Q7896139` is the School of Medicine's own item, and per §2 the unit's QID does not belong in this
column — `Q235034` (the university) belongs on all four rows. One ranked institution with two QIDs cannot attach a profile:
the build raises `BuildFailure` on the route as soon as either QID gains an `affiliations` row.

**Query C — apostrophe and punctuation twins.** BINARY collation makes `'` (U+0027) and `’` (U+2019) different
institutions. The fuzzy `--suggest` mode of the normalizer scores these around 0.97 and will surface them, but the
`AFFILIATIONS` disjointness guard compares raw strings and will not:

```sql
SELECT affiliation_name, replace(replace(affiliation_name, '’', "'"), '`', "'") AS folded, count(*)
FROM awards WHERE affiliation_name LIKE '%''%' OR affiliation_name LIKE '%’%'
GROUP BY 1 ORDER BY folded;
```

Both forms are live: `Boston Children's Hospital` (straight) sits beside `Boston Children’s Hospital/Harvard Medical
School` (curly), and `Brigham and Women’s`, `King’s College London`, `Children’s Hospital of Philadelphia` are curly
while `Queen's University`, `Guy's Hospital`, `St. Jude Children's Research Hospital` are straight. Fold before comparing;
never normalize the stored value on a whim, because the institution's own spelling is the authority.

### 7.2 Spot checks worth keeping

```sql
-- a parent and its units
SELECT affiliation_name, affiliation_sub_name, count(*) FROM awards WHERE affiliation_name = 'Harvard University' GROUP BY 1, 2;

-- intended multi-city parents — confirm, do not "fix" (§4.4)
SELECT affiliation_name, affiliation_city, count(*) FROM awards WHERE affiliation_name IN ('Harvard University', 'Cornell University') GROUP BY 1, 2;

-- a sub-name that EQUALS its parent is always a defect (6 rows today, all University College London)
SELECT affiliation_name, count(*) FROM awards WHERE affiliation_sub_name = affiliation_name AND affiliation_name <> '' GROUP BY 1;
```

## 8. Live counts

**Snapshot: 20260728, `datasets/awards.sqlite3` working tree (uncommitted).** Every number in this file — here, in the §7
check table, and in §9 — is from this snapshot and starts drifting the moment the next write lands. Re-measure before
quoting any of it as current; treat them as the baseline to diff against, not as facts.

| Fact | Count |
|---|---:|
| `awards` rows | 3093 |
| Rows with a nonblank `affiliation_name` | 2766 |
| Distinct parent institution names | 731 |
| Rows with a nonblank `affiliation_sub_name` | 375 |
| Parents carrying at least one unit | 52 |
| Rows with a nonblank `affiliation_wikidata_qid` | 2341 |
| Rows where `affiliation_wikidata_qid IS NULL` | 750 |
| `award_extra_affiliations` rows | 84 |
| Awards carrying an extra affiliation | 56 |
| Highest position in use | 14 |
| `affiliations` profiles | 304 (logo 133, description 300, application URL 303) |
| Rows using `;` in any affiliation column | 0 |

## 9. Known hazards — flagged, not fixed

- **`normalize_affiliations.py --apply` would today rewrite 149 UC rows.** The entry
  `"University of California": ("University of California (campus unspecified)", "")` predates the UC hierarchy work,
  which made `University of California` the ranked *parent* of 13 campus sub-names. A dry run reports
  `alias rows=149 'University of California' -> 'University of California (campus unspecified)'`. Running `--apply`
  without removing that entry destroys the campus hierarchy. **Dry-run first, every time.**
- **The campus roll-up was applied as a data operation, not through the normalizer.** The two therefore disagree; the
  database is the source of truth and the mapping table has not caught up.
- **Three QIDs are ambiguous and must not be "fixed" by aliasing until their rows are reviewed one by one.** Each surfaces
  in §7 Query A; each needs the row's city and year checked against the item before anything is merged:

  | QID | Names on it | Rows | The question |
  |---|---|---:|---|
  | `Q152087` | `Berlin University`, `University of Berlin`, `Humboldt University of Berlin`, `Humboldt-Universität zu Berlin` | 14 | Humboldt is the continuator, but a post-1948 row may belong to Freie Universität Berlin instead |
  | `Q1586184` | `JILA`, `University of Colorado, JILA` | 4 | JILA is a joint NIST/CU institute. A row may be NIST-side or CU-side, and the two are different affiliations |
  | `Q280413` | `CNRS (VERIMAG)`, `Centre National de la Recherche Scientifique`, `French National Centre for Scientific Research (CNRS)` | 3 | VERIMAG is a specific Grenoble lab, not CNRS itself. The other two are one institution in two languages and are a plain alias |

  Only `Q1586184` overlaps the `sub-name-is-the-institution` list; the other two are invisible to every current check.
- **`'` and `’` are different institutions to SQLite.** `Q1164246` (St. Jude Children's, 4 rows) and `Q1000479` (Boston
  Children's, 2 rows) are the QIDs where both forms are in play. The normalizer's `--suggest` scores such pairs ~0.97 and
  will offer them; its disjointness guard compares raw strings and will not catch a curly-apostrophe duplicate. §7 Query C.
- 16 groups trip `sub-name-is-the-institution`, but only 3 of them are defects (§7). Exact sub-name-equals-parent is
  6 rows, all `University College London`.
- `The Ohio State University` carries both `Columbus` and `Columbus, OH`; 70 groups use the `City, ST` form against the
  bare-city house style.
- **Country centroids are in use as placeholder coordinates.** A point repeated across many rows, or written in round
  numbers, is a country centre standing in for an unknown place — not data. It hides the gap, because the cell is not
  blank and no check counts it. Found in `birth_coordinates`; the same failure can reach affiliation coordinates.
  29 rows remain, and country does not bound it: one United Kingdom row carries the US centre.

  | Point | Country it centres | Rows |
  |---|---|---:|
  | `-98.5795,39.8282` | United States | 18 |
  | `35.0000,31.0000` | Israel | 5 |
  | `-2.0000,54.6000` | United Kingdom | 4 |
  | `136.0000,35.0000` | Japan | 1 |
  | `105.0000,35.0000` | China | 1 |

  To find more: group any coordinate column and read the values shared by rows whose city differs or is blank.

- `Washington University`, `Washington University in St. Louis`, and `Washington University Genome Sequencing Center` are
  one place spelled three ways. Merging them needs care — `Washington University` is also a roll-up target, so a careless
  alias breaks the disjointness invariant and splits the institution across two names.

## 10. Known script bugs — flagged, not fixed

Defects in the tooling rather than in the data. §9 is data; this is code.

- **`scripts/enrich_application_urls.py` will destroy curated data. Do not run it.** It takes no backup, recomputes every
  row from a hardcoded dict, and queues an UPDATE for every row whose stored value differs from the computed one —
  **including overwriting a curated URL with `''`** when the QID is absent from the dict. Its dry run proposes 145 updates
  against 304 rows, essentially all of them over nonblank values. Its fallback also writes
  `https://www.wikidata.org/wiki/<QID>` as an "application URL" for any profile whose description contains "university",
  which is not an application URL. Fixing it means a backup, a blank-only guard, and dropping the fallback.

- **`scripts/enrich.py:236-243` invents exact dates from imprecise Wikidata statements.** `iso_date` trims a timestamp
  only when it ends `-00-00` or `-00`, but Wikidata never emits zeros for low precision: it writes a canonical
  `YYYY-01-01` and states the real precision in a sibling `precision` field, which `claim_time` (`:223-229`) drops before
  `iso_date` sees it. So precision 9 (year) becomes an exact 1 January date, and precision 7 (century) becomes both a
  date and a `birth_year` — `Q2636489` Alain Townsend arrived as born 2000-01-01, having been elected FRS in 1992.
  Live effect: 55 birth dates and 3 death dates end `-01-01`, most of them invented; a sample of 12 was 11 imprecise to
  1 genuine. Fixing it means carrying `precision` through `claim_time` and truncating on it — 11 day, 10 month, 9 year,
  ≤8 blank. Until then every enrichment run recreates them, and a `-01-01` date cannot be trusted without rechecking
  the item.

- **`scripts/normalize_affiliations.py:93` normalizes MSKCC the wrong way.**

  ```python
  "Memorial Sloan Kettering Cancer Center": ("Memorial Sloan-Kettering Cancer Center", ""),
  ```

  The English Wikipedia title is **`Memorial Sloan Kettering Cancer Center`** — no hyphen; the institution dropped it when
  it rebranded. The mapping takes the correct modern name as its *source* and rewrites it to the historical hyphenated
  form, against the house rule that places use today's name. The direction of the entry should be reversed. Live effect
  today: `Q1808012` carries both spellings (7 hyphenated rows, 2 not) and appears in §7 Query A, and a `--apply` run
  would convert the remaining 2 correct rows to the wrong form.
