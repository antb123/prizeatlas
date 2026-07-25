# Affiliation sub-name — rolling constituent units into their parent university

## Goals

Rank institutions by the institution, not by which of its schools a laureate happened to be recorded under, while keeping the specific unit visible. Harvard currently sits in five separate places on `/affiliations/`; it should sit in one, and still show that 18 of its laureates came through the Medical School.

## Background

`affiliation_name` holds one free-text string per award record. Where the source recorded a constituent unit rather than the institution — `Harvard Medical School`, `Stanford University School of Medicine`, `Johns Hopkins University School of Medicine` — the unit competes with its own parent in the `/affiliations/` ranking. Harvard is split across `Harvard University` (66 rows), `Harvard Medical School` (21), `Harvard School of Public Health` (2), `Harvard University, Lyman Laboratory` (1) and `Harvard University, Biological Laboratories` (1), and so ranks below its true standing.

`scripts/normalize_affiliations.py` already solves the adjacent problem — one institution spelled several ways — with a hand-written `ALIASES` table (`normalize_affiliations.py:24-75`). Its doc comment states the governing principle: mappings are *written out rather than derived*, because a text rule that strips a trailing clause would also merge `University of California, Berkeley` into `University of California`. That principle carries over unchanged.

The current table stops deliberately at the school boundary — `normalize_affiliations.py:67` maps `"Johns Hopkins University, School of Medicine"` to `"Johns Hopkins University School of Medicine"`, not to the university. This spec reverses that decision.

Collapsing the unit into the parent would destroy information. Adding a second column keeps both.

### Why a stored column rather than a build-time map

The roll-up could live entirely in `build.py` as a dict applied during `plan_places`, adding no column and no migration — roughly 30 LOC in one file instead of ~95 across five. That option was considered and rejected, and the reasoning is recorded here because the choice is otherwise invisible:

`ALIASES` already normalizes affiliations *in the database*, and every consumer of this data — the site build, ad-hoc SQL, future exports — should see the same canonical institution. Splitting normalization across two layers, half in the DB and half in the renderer, would mean a `SELECT affiliation_name` returns something the website disagrees with. One obvious control path argues for putting it where the existing normalization already is.

The cost is real and accepted: `affiliation_sub_name` is derived data stored alongside its source, which is the one place this design lets the data disagree with itself. The mitigations are that exactly one script writes it (§Normalizer) and that re-running is a no-op.

## Assumptions

1. **(Load-bearing)** Only *constituent* units roll up — a school, college, faculty, department, laboratory, or institute that is legally part of the named parent. Legally independent institutions stay standalone even when closely tied: Massachusetts General Hospital, Brigham and Women's Hospital, Mayo Clinic, St. Jude, Baylor College of Medicine (separated from Baylor University in 1969), New York Medical College, London School of Economics. If this boundary moves, the whole mapping table changes.
2. **(Load-bearing)** The mapping is hand-written and reviewed, never pattern-derived. The pattern sweep used to *find* candidates returns 78 names, of which at least 16 must not be merged — including two government bodies (`Department of Scientific and Industrial Research`, `Bureau of Public Health Nursing New York State Department of Health`). A rule that merged on `"School of"` would be wrong roughly a fifth of the time.
3. `awards.sqlite3` is the sole source of truth. `scripts/import_sqlite.py` has been deleted, the CSV snapshots are archived under `old/`, and there is no import path back from CSV. There is therefore no second schema definition to keep in sync — the migration below is the whole schema change.
4. The schema now lives only in the database. `tests/test_enrich_json.py` holds a local fixture copy for its temporary databases; it does not need the new column, because `enrich.py` never touches affiliation fields.
5. The 49 compound `;`-separated affiliation strings are out of scope. They are a different problem — one row naming several institutions — that a second column does not solve. Five of them contain a unit clause and will not roll up.
6. `affiliation_sub_name` is single-valued free text, consistent with every other column in this table. No units lookup table, no foreign key: the change touches 109 of 3,091 rows, and a lookup table would add the codebase's first join to serve 3.5% of the data while removing none of the hand judgement.
7. `build.py:400-407` counts distinct laureates per affiliation, not award records. Sub-unit counts therefore need not sum to the parent count.
8. Nothing but `normalize_affiliations.py` writes `affiliation_name` or `affiliation_sub_name`. `enrich.py` does not: `WRITE_FIELDS` and `DATABASE_WRITE_FIELDS` (`enrich.py:104-111`) cover birth, death, sex and type only, and its docstring states affiliation is left to other passes. The normalizer MUST still be idempotent, because it is run repeatedly by hand.

## Scope

~90 LOC across 4 files, plus a one-statement schema migration.

| File | Change | LOC |
|---|---|---|
| `awards.sqlite3` | `ALTER TABLE` migration, run once | 1 stmt |
| `scripts/normalize_affiliations.py` | widen `ALIASES` to `AFFILIATIONS`, 50 unit entries, disjointness guard, migration guard | ~70 |
| `website/build.py` | column, dataclass field, breakdown in `plan_places`, description, JSON-LD | ~20 |
| `website/templates/winner.html` | render the unit under the parent | ~3 |
| `website/templates/affiliations.html` | nested sub-unit rows | ~6 |

## Data model

```
affiliation_name      "Harvard University"      canonical parent — what /affiliations/ ranks on
affiliation_sub_name  "Harvard Medical School"  the unit as recorded — displayed, never ranked
```

`affiliation_sub_name` MUST default to `''`.

**Blank means "this script did not roll the record up."** That is a fact about the pipeline and is always true. It does NOT mean "the record named an institution directly" — blank also covers the 16 deliberate non-merges (§Explicitly not merged), which *are* units held out for policy reasons, and the five deferred compounds that contain a unit clause. Stating the weaker, true thing keeps a later reader from treating blank as evidence about the source data.

### Geo columns are NOT rolled up

**This is the sharpest edge in the change.** Roll-up rewrites `affiliation_name` and deliberately leaves `affiliation_city`, `affiliation_country` and `affiliation_coordinates` describing the *unit*. After the merge, one parent name legitimately carries several cities:

```
Harvard University  ← Harvard Medical School        Boston      (21 rows)
Harvard University  ← Harvard University            Cambridge   (66 rows)
Cornell University  ← Weill Cornell Medical College New York    (4 rows)
Cornell University  ← Cornell University            Ithaca      (19 rows)
```

Cornell ends up holding Ithaca and New York City — 220 miles apart — under one name. This is **intended**: the geo columns are record-level and answer "where was this laureate at the time", which is Boston for a Medical School laureate. Blanking them on roll-up would destroy correct information.

The consequence MUST be stated because it is a trap: anyone who later writes `SELECT DISTINCT affiliation_name, affiliation_city` will find Harvard in two cities and reasonably try to "fix" it. Any future per-institution page or map keyed on `affiliation_name` MUST pick a representative location explicitly rather than assuming one exists.

`University of California School of Medicine` (San Francisco ×3, Los Angeles ×1) rolls into `University of California (campus unspecified)`, which already spans six campuses. This is the one merge that loses resolvable information — UCSF and UCLA become "campus unspecified" — and it is accepted only because the existing alias at `normalize_affiliations.py:53` already established that bucket.

### Migration

The table is `STRICT`, so the column MUST be declared `TEXT` with a non-null default:

```sql
ALTER TABLE awards ADD COLUMN affiliation_sub_name TEXT NOT NULL DEFAULT '';
```

This is the entire schema change. With the importer deleted (Assumption 3) there is no second column list to update, and `ALTER TABLE` appending the column last is simply where it lives.

## Normalizer

### One table, not two

`ALIASES` becomes `AFFILIATIONS: dict[str, tuple[str, str]]`, source → `(canonical_name, sub_name)`, where an empty sub-name means a pure spelling alias:

```python
AFFILIATIONS = {
    "Massachusetts Institute of Technology (MIT)": ("Massachusetts Institute of Technology", ""),
    "Harvard Medical School":                      ("Harvard University", "Harvard Medical School"),
}
```

The alternative — a second `UNITS` table applied after `ALIASES` — was rejected. It required a stated ordering rule, a two-hop path for the comma forms (`"Johns Hopkins University, School of Medicine"` → alias → unit), a second apply function, and a second report line type. One table deletes all of that for the cost of mechanically widening the 46 existing entries to `("X", "")`. Two mechanisms that must run in a fixed order, where entries in the first exist only to feed the second, is one mechanism wearing two hats.

The two entries at `normalize_affiliations.py:67-68` are **rewritten in place, not deleted** — the comma forms map straight to `("Johns Hopkins University", "School of Medicine")`. Deleting them would silently drop those strings on any rebuild from CSV.

### The disjointness invariant MUST be enforced in code

The design rests on: *no target is ever a source.* That is what makes one pass sufficient and re-running a no-op. It holds today, but it is one edit away from breaking, and the break is silent.

The loaded gun is in §Adjacent findings: `Washington University` (6 rows) should become an alias for `Washington University in St. Louis`, and `Washington University` is also a **parent** in this table. Act on that note and a single run gives you — alias rewrites the 6 existing rows, then the unit entry *creates* a fresh `Washington University` row from `Washington University School of Medicine`. The institution ends up split across two names, and convergence needs a second run, violating the idempotence requirement.

A module-level guard clause MUST assert the invariant so a future edit fails loudly at startup rather than silently splitting data:

```python
_targets = {name for name, _ in AFFILIATIONS.values()}
if overlap := _targets & set(AFFILIATIONS):
    raise NormalizeFailure(f"affiliation target is also a source: {sorted(overlap)}")
```

The spec asserted this property in prose in its first draft and never enforced it. Two lines convert a future data corruption into a startup failure.

### sub_name naming rule

`sub_name` is a display string doing duty as a grouping key in `plan_places`, so it MUST be stable across spellings of the same unit. **The rule: use the unit's current canonical name, not the name as recorded.** Otherwise the fragmentation this spec removes reappears one level down:

| Recorded | sub_name | Why |
|---|---|---|
| `Cornell University Medical College` (3) | `Weill Cornell Medical College` | Same school, renamed 1998 — one bucket, not two |
| `Weill Cornell Medical College` (1) | `Weill Cornell Medical College` | |
| `University of Massachusetts Medical School` (5) | `UMass Chan Medical School` | Same school, renamed 2021 |
| `UMass Chan Medical School` (1) | `UMass Chan Medical School` | |
| `Yale University School of Medicine` (3) | `School of Medicine` | |
| `Yale School of Medicine` (2) | `School of Medicine` | |

How full the name is written varies by parent — `Harvard Medical School` reads correctly in full, `School of Medicine` reads correctly under `Johns Hopkins University`. That inconsistency is accepted: the table is hand-written, and each entry is judged for how it reads beneath its own parent.

### The unit entries

50 entries, 109 rows. Parents in **bold** do not yet exist as affiliation values in the 2026-07-25 snapshot and will be created by the merge — correct, since the institution earned the affiliation and only its unit was recorded.

| Source | → parent | sub_name | rows |
|---|---|---|---|
| Harvard Medical School | Harvard University | Harvard Medical School | 21 |
| Harvard School of Public Health | Harvard University | Harvard School of Public Health | 2 |
| Harvard University, Lyman Laboratory | Harvard University | Lyman Laboratory | 1 |
| Harvard University, Biological Laboratories | Harvard University | Biological Laboratories | 1 |
| Johns Hopkins University School of Medicine | Johns Hopkins University | School of Medicine | 11 |
| Johns Hopkins University, School of Medicine | Johns Hopkins University | School of Medicine | 0 |
| Johns Hopkins University, School of Hygiene and Public Health | Johns Hopkins University | School of Hygiene and Public Health | 1 |
| Johns Hopkins Institute for Cell Engineering | Johns Hopkins University | Institute for Cell Engineering | 1 |
| McKusick-Nathans Institute of Genetic Medicine at the Johns Hopkins University | Johns Hopkins University | McKusick-Nathans Institute of Genetic Medicine | 1 |
| Stanford University School of Medicine | Stanford University | School of Medicine | 10 |
| Department of Biology, Stanford University | Stanford University | Department of Biology | 1 |
| University of Massachusetts Medical School | **University of Massachusetts** | UMass Chan Medical School | 5 |
| UMass Chan Medical School | **University of Massachusetts** | UMass Chan Medical School | 1 |
| University of California School of Medicine | University of California (campus unspecified) | School of Medicine | 4 |
| University of Pennsylvania School of Medicine | University of Pennsylvania | School of Medicine | 4 |
| Perelman School of Medicine, University of Pennsylvania | University of Pennsylvania | Perelman School of Medicine | 1 |
| University of Pennsylvania, Department of Landscape Architecture and Regional Planning | University of Pennsylvania | Department of Landscape Architecture and Regional Planning | 1 |
| Cornell University Medical College | Cornell University | Weill Cornell Medical College | 3 |
| Weill Cornell Medical College | Cornell University | Weill Cornell Medical College | 1 |
| Emory University School of Medicine | Emory University | School of Medicine | 3 |
| Emory University Rollins School of Public Health | Emory University | Rollins School of Public Health | 1 |
| Yale University School of Medicine | Yale University | School of Medicine | 3 |
| Yale University, School of Medicine | Yale University | School of Medicine | 0 |
| Yale School of Medicine | Yale University | School of Medicine | 2 |
| Vanderbilt University School of Medicine | Vanderbilt University | School of Medicine | 2 |
| Vanderbilt University Medical School | Vanderbilt University | School of Medicine | 1 |
| University of Washington School of Medicine | University of Washington | School of Medicine | 2 |
| University of Washington, Department of Atmospheric Sciences | University of Washington | Department of Atmospheric Sciences | 1 |
| Boston University School of Medicine | **Boston University** | School of Medicine | 1 |
| Kobe University School of Medicine | Kobe University | School of Medicine | 1 |
| Graduate School of Medicine, Osaka University | Osaka University | Graduate School of Medicine | 1 |
| Graduate School of Frontier Bioscience, Osaka University | Osaka University | Graduate School of Frontier Bioscience | 1 |
| New York University School of Medicine | New York University | School of Medicine | 1 |
| New York University, College of Medicine | New York University | School of Medicine | 1 |
| NYU Stern School of Business | New York University | Stern School of Business | 1 |
| University of Michigan Medical School | University of Michigan | Medical School | 1 |
| University of Pittsburgh School of Medicine | University of Pittsburgh | School of Medicine | 1 |
| University of Utah School of Medicine | University of Utah | School of Medicine | 1 |
| University of Cincinnati College of Medicine | **University of Cincinnati** | College of Medicine | 1 |
| Washington University School of Medicine | Washington University | School of Medicine | 1 |
| Western Reserve University School of Medicine | Western Reserve University | School of Medicine | 1 |
| Tufts Medical College | Tufts University | Medical College | 1 |
| University of Paris School of Medicine | University of Paris | School of Medicine | 1 |
| The John Curtin School of Medical Research, The Australian National University | Australian National University | John Curtin School of Medical Research | 1 |
| University of Nottingham, School of Physics and Astronomy | **University of Nottingham** | School of Physics and Astronomy | 1 |
| University of Reading, Department of Meteorology | **University of Reading** | Department of Meteorology | 1 |
| University of Ghent, Department of Genetics | Ghent University | Department of Genetics | 1 |
| University of Maryland, Department of Economics and School of Public Policy | University of Maryland | Department of Economics and School of Public Policy | 1 |
| École normale supérieure, Department of Geology | École Normale Supérieure | Department of Geology | 1 |
| Weizmann Institute of Science, Department of Computer Science and Applied Mathematics | Weizmann Institute of Science | Department of Computer Science and Applied Mathematics | 1 |
| University of California San Diego, School of Medicine, Department of Pediatrics | University of California, San Diego | School of Medicine, Department of Pediatrics | 1 |
| Ruijin Hospital, School of Medicine, Shanghai Jiao Tong University | **Shanghai Jiao Tong University** | Ruijin Hospital, School of Medicine | 1 |

Two entries show 0 rows: the comma forms carried over from `normalize_affiliations.py:67-68`, already applied in the live DB and retained against a CSV rebuild.

The parent for the geology department is **`École Normale Supérieure`** (title case). The lowercase `École normale supérieure` does not exist in the database — SQLite's BINARY collation makes them different values, and using the lowercase form would create a second spelling of the same school. Three other ENS strings exist (`École Normale Supérieure Paris-Saclay`, `École Normale Supérieure de Lyon and Institut Henri Poincaré, France`) and are left alone.

Confirm rather than trusting the bolded list, which drifts:

```sql
SELECT DISTINCT affiliation_name FROM awards
 WHERE affiliation_name IN ('University of Massachusetts', 'University of Cincinnati', 'University of Nottingham',
                            'Boston University', 'University of Reading', 'Shanghai Jiao Tong University');
```

### Explicitly not merged

These MUST stay standalone. This table SHOULD be carried into `normalize_affiliations.py` as a comment block above `AFFILIATIONS`, where the existing table already keeps its rationale inline (`normalize_affiliations.py:22-23, 41-42, 52`) — it protects nothing sitting in a spec that nobody has open while editing the table.

| Name | Reason |
|---|---|
| London School of Economics (+ `…and Political Science`) | Constituent of the University of London, but universally ranked as its own institution |
| Stockholm School of Economics | Independent |
| The Netherlands School of Economics | Independent; later merged into Erasmus University, not the same entity at award time |
| Toulouse School of Economics (TSE) | Grande école, ranked standalone |
| Baylor College of Medicine | Separated from Baylor University in 1969 |
| New York Medical College | Independent |
| Albert Einstein College of Medicine | Left Yeshiva University; independent |
| Medical College of Georgia | Parent (Augusta University) absent from the data |
| Jefferson Medical College | Parent (Thomas Jefferson University) absent from the data |
| Department of Scientific and Industrial Research | UK government body, not a university unit |
| Bureau of Public Health Nursing New York State Department of Health | Government body |
| Research Division of Infectious Diseases, Children's Medical Center | Hospital unit, no university parent |
| École municipale de physique et de chimie industrielles | ESPCI Paris, standalone |
| Max-Planck-Institut für Züchtungsforschung, Department of … | Research institute, not a university |
| CSIRO, Division of Marine Research | Government research agency |
| Laboratories of the Division of Medicine and Public Health, Rockefeller Foundation | Foundation, not a university |
| St. Petersburg Department of the Steklov Institute of Mathematics | Research institute |

### Deferred

Compound or ambiguous strings, out of scope per Assumption 5:

`Harvard Medical School, Massachusetts General Hospital` · `Harvard Medical School, Children's Cancer Research Foundation` · `Harvard Medical School; Beth Israel Hospital` · `Harvard Medical School; Howard Hughes Medical Institute` · `Harvard Medical School; Weill Cornell Medical College` · `Harvard University; Howard Hughes Medical Institute` · `American Heart Association Harvard Medical School` · `Boston Children's Hospital/Harvard Medical School` · `Dana-Farber Cancer Institute, Harvard Medical School` · `Mt. Sinai School of Medicine, CUNY` · `London University, King's College Hospital Medical School` · `University of Chicago, University of Cincinnati College of Medicine` · `New York University School of Medicine, Office of Defense Mobilization, New York Times` · `University of Illinois School of Medicine` (campus ambiguous) · `University of Texas Medical School at Houston` (UTHealth is a distinct institution) · `Institut d'Optique Graduate School – Université Paris-Saclay`

### Adjacent findings — not fixed here

Noted, not actioned, per "flag issues instead of fixing them":

- `Washington University` (6), `Washington University in St. Louis` (1) and `Washington University Genome Sequencing Center` (1) are one place spelled three ways. Fixing this REQUIRES care — see §The disjointness invariant.
- `UT Southwestern Medical Center` appears in four spellings across 11 rows.
- `Baylor University College of Medicine` is the historical name of `Baylor College of Medicine`.
- `Harvard Medical School, Massachusetts General Hospital` carries `affiliation_city = New York`. HMS and MGH are both in Boston; this is a geocoding error.
- `University of Paris` carries 1986, 2000 and 2003 rows for an institution dissolved in 1970, and `University of Paris, France` (1966) is an unmapped alias.

### Reporting

`--apply` MUST remain opt-in and MUST continue to back up first via `back_up()` (`normalize_affiliations.py:125-129`). Output keeps the existing grep-able `key=value` style:

```
affiliations unit  rows= 21 'Harvard Medical School' -> 'Harvard University' + 'Harvard Medical School'
affiliations normalize dry-run entries=96 alias_rows=0 unit_rows=109 compound=49
```

`report()` (`normalize_affiliations.py:90-98`) and the unused-source warning (`:170-172`) MUST cover the unit entries too. This matters more than it looks: a dry run today prints `unused=46` — every existing alias is already applied — and the unit entries reach that state one run after landing. Without unused reporting there is nothing to distinguish "already applied" from "the source string drifted and this entry silently stopped matching".

The `compound=49` counter is a summary only; the per-row dump is not worth a permanent code path for a problem this spec defers.

Illustrative numbers above are shapes, not expected output — `report()` counts *matching* entries, so today's real alias count is 0.

### Failure paths

`apply_aliases()` (`normalize_affiliations.py:132-147`) writes both columns in one statement per entry, in one transaction, followed by the existing `PRAGMA integrity_check`.

The update MUST NOT be guarded with `AND affiliation_sub_name = ''`. The column is derived and owned by this script — an unguarded write *is* the definition of idempotent here, and nothing else writes it (Assumption 8). No hand-entered value is at risk.

A guard clause MUST check the column exists **before** `back_up()`, so an unmigrated database fails with a log line naming the fix instead of raising mid-transaction and leaving a junk `.bak` behind:

```
affiliations normalize failed: column affiliation_sub_name missing, run the migration
```

**Ordering is mandatory: migration → normalizer → build.** The `build.py` and template changes MUST NOT deploy ahead of the `ALTER TABLE`; `build.py:283` would raise `no such column`.

## Website

- `AWARD_COLUMNS` (`build.py:91-93`) and `AwardRecord` (`build.py:134-136`): add `affiliation_sub_name`. The real constraint is **not** column order — `build.py:298` looks values up by name (`row[field.name]`) — but that every `AwardRecord` field name MUST appear in `AWARD_COLUMNS`, or that lookup raises.
- `plan_places` (`build.py:393-420`) currently builds `by_affiliation: dict[str, set[str]]` (`:400`). Rekey it to `dict[tuple[str, str], set[str]]` on `(parent, sub_name)` — **one structure, not two**. A parent's rank count is the union of its buckets, which makes Assumption 7's non-summing property evident in the code rather than only in a comment. Returning a parallel breakdown dict alongside the existing one would create two structures that must agree.
- `plan_places` returns a 2-tuple, unpacked at `build.py:785` and consumed at `:825`; the template iterates `{% for name, count in affiliations %}` (`affiliations.html:12`). All four sites change.
- Ranking MUST stay on the parent, by distinct laureate. It MUST NOT be re-derived by summing buckets — a laureate recorded under both a school and the university proper would be counted twice.
- Winner description (`build.py:720-721`): where a sub-name exists, `At the time: {sub_name}, {name}.` `DESCRIPTION_LIMIT` is 160 (`build.py:59`); the longest sub-name costs 78 characters and squeezes the motivation. Long sub-names SHOULD be dropped from the description rather than the motivation.
- JSON-LD (`build.py:351-352`): the `Organization` `name` MUST remain the parent. schema.org's `department` expects an `Organization`, not text:
  ```python
  payload["affiliation"] = {"@type": "Organization", "name": record.affiliation_name}
  if _nonblank(record.affiliation_sub_name):
      payload["affiliation"]["department"] = {"@type": "Organization", "name": record.affiliation_sub_name}
  ```
- `AFFILIATION_BLOCKLIST` (`build.py:57`) needs no change — `build.py:406` tests `affiliation_name`, which is the parent after roll-up.

### Rendering the breakdown

```
Harvard University                      79
   Harvard Medical School               18
   Harvard School of Public Health       2
```

The `''` bucket MUST be suppressed. Only ~30 of 830 parents have any unit at all; rendering "unit not recorded: N" under the other 800 would restate the parent count as a child row. With the blank bucket gone and two or three real units under Harvard, nobody reads the children as a partition, so the template needs no disclaimer.

Parents with no non-blank sub-name render exactly as today.

### Behavior / Acceptance

#### Requirement: Ranking — `/affiliations/` MUST rank by parent institution

##### Scenario: Harvard's five entries become one
- WHEN the site is built after the normalizer has run
- THEN `/affiliations/` lists `Harvard University` once with **80 laureates**
- AND `Harvard Medical School`, `Harvard School of Public Health`, `Harvard University, Lyman Laboratory` and `Harvard University, Biological Laboratories` do not appear as their own top-level rows
- AND the six deferred `Harvard …;…` compound strings DO still appear separately (Assumption 5) — this change does not reduce Harvard to a single row, only to one ranked institution plus its deferred compounds

The count is 80, not 91. The page ranks distinct laureates, not award records (Assumption 7): the five merged entries hold 91 *rows* but 80 distinct laureate QIDs. This change MUST NOT alter the ranking unit from laureates to rows.

#### Requirement: Breakdown — a ranked row MUST show its recorded units

##### Scenario: Harvard shows its units
- WHEN `Harvard University` is rendered on `/affiliations/`
- THEN `Harvard Medical School` is listed beneath it with 18 laureates
- AND no "unit not recorded" row is rendered

#### Requirement: Preservation — the recorded unit MUST survive on the person page

##### Scenario: A Harvard Medical School laureate
- WHEN a winner page renders for a record whose source said `Harvard Medical School`
- THEN the Affiliation section shows the Medical School and Harvard University
- AND the city still reads Boston, not Cambridge (§Geo columns)
- AND no laureate loses affiliation detail that was present before the change

#### Requirement: Idempotence — the normalizer MUST be safe to re-run

##### Scenario: Second run changes nothing
- WHEN `normalize_affiliations.py --apply` runs twice in succession
- THEN the second run reports `unit_rows=0`
- AND every `affiliation_sub_name` is unchanged

#### Requirement: Invariant — a target MUST NOT also be a source

##### Scenario: A future alias collides with a parent
- WHEN an entry is added whose target is already a key in `AFFILIATIONS`
- THEN the script raises `NormalizeFailure` at import and exits non-zero
- AND no database write is attempted

## Verification

```sql
-- Harvard consolidated, with its units intact
SELECT affiliation_name, affiliation_sub_name, count(*) FROM awards
 WHERE affiliation_name = 'Harvard University' GROUP BY 1, 2;

-- the intended multi-city parents — confirm, do not "fix" (§Geo columns)
SELECT affiliation_name, affiliation_city, count(*) FROM awards
 WHERE affiliation_name IN ('Harvard University', 'Cornell University') GROUP BY 1, 2;
```

Distinct affiliation names falling from 875 to about 831 is **informational, not pass/fail** — 50 sources removed, 6 parents created, and an `ALIASES` run between now and implementation moves the baseline.
