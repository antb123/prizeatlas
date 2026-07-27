# award_extra_affiliations — a second affiliation per award (20260727)

Prerequisite context: `datasets-affiliation-todo-20260727.md`.

**`feat/map-mvp` is assumed dead.** This work branches from `main`.

## Goals

Let an award carry more than one affiliation, and populate the reviewed second affiliations in the same change — so the institution rankings stop being wrong.

## Background

`awards` holds one affiliation per row in six columns (`website/build.py:119-124`, mirrored as `AwardRecord` fields at `:168-173`). Second affiliations therefore hide in remarks prose, in `affiliation_sub_name`, and in slash-joined names, and the `/affiliations/` ranking under-counts every institution that is usually somebody's second address.

An earlier draft of this spec backfilled all 2770 affiliations into a new child table, dropped the six flat columns, and rewrote five maintenance scripts — 12 files, ~300 LOC, and zero new affiliations. It was rejected: it performed a destructive migration without fixing the problem.

This design keeps the flat columns as position 1 and adds only what is missing. The two stores are **disjoint** — flat *is* position 1, the table *is* positions 2+ — so no fact exists twice and there is nothing to drift.

Measured state of `datasets/awards.sqlite3`:

| Fact | Count |
|---|---|
| `awards` rows | 3093 |
| Rows with a non-blank `affiliation_name` | 2766 |
| Rows with a non-blank `affiliation_sub_name` | 277 |
| Named rows where `affiliation_wikidata_qid IS NULL` | 436 |
| Rows using the `;` multi-value convention in any affiliation column | 0 |
| Distinct laureates at Howard Hughes Medical Institute today | 2 |
| Distinct laureates at University of California, Berkeley today | 27 |

The HHMI and Berkeley figures are the ones this change moves. Earlier drafts of this spec quoted 4 and 34; those were inherited from `datasets-affiliation-todo-20260727.md` and do not survive checking.

## Assumptions

1. **(Load-bearing)** Position is a stable sort key, not a rank. Position 1 living in the flat columns is a storage detail, not a claim of primacy — everything above `read_database()` sees one uniform tuple.
2. **(Load-bearing)** Only reviewed affiliations are loaded. The input is a committed TSV, not a prose parser. Rows that were not reviewed by hand do not go in.
3. **(Load-bearing)** The flat columns are NOT dropped and NOT rewritten. No maintenance script changes.
4. Unknown QIDs and locations stay blank. Never borrow either from a same-named row — that is what split Berkeley 34/28.
5. The site output **will** change, by exactly the reviewed additions. Byte-identity is not the gate here; a reviewed delta is.
6. `affiliation_wikidata_qid` holds SQL `NULL` on 436 rows. `_text()` at `:640` already flattens this on read, so composition inherits the existing behaviour and no migration is needed.

## Scope

6 files, ~150 LOC.

| File | Change | Approx. LOC |
|---|---|---|
| `scripts/load_extra_affiliations.py` | New. Create the table, load a reviewed TSV, report counts. | ~50 new |
| `website/build.py` | Compose flat + extras; iterate the tuple in every consumer. | ~70 changed |
| `website/templates/affiliation.html` | Unpack the new award-link shape. | ~5 changed |
| `website/templates/winner.html` | Loop affiliations instead of reading scalars. | ~12 changed |
| `tests/test_build_website.py` | Two fixture helpers; one new multi-affiliation test. | ~35 changed |
| `scripts/validate_awards.py` | Affiliation checks cover both stores via one CTE. | ~25 changed |

Out of scope: institution deduplication, dropping the flat columns, and the `affiliations` metadata table.

**Baseline warning.** `scripts/validate_awards.py` is untracked. Its line references below have no committed baseline and MUST be committed as-is before implementation.

## Schema

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

`CHECK (position >= 2)` is what makes the two stores disjoint by construction. Full location columns are carried per row so nothing is ever resolved by joining on an institution name.

No `CHECK (coordinates = '' OR wikidata_qid <> '')` — hand-verified coordinates without a QID are legitimate. SQLite does not enforce the foreign key unless `PRAGMA foreign_keys = ON`, which this codebase does not set; the clause is documentation, and orphan detection belongs in the validator.

## Data flow

```
awards.affiliation_*  ──┐
  (position 1)          ├──→  read_database()  ──→  record.affiliations: tuple[AwardAffiliation, …]
award_extra_affiliations├──→   composes once            │
  (positions 2+)      ──┘                               ▼
                                    plan_places → Affiliation.awards: tuple[AwardLink, …]
                                                        (record, affiliation, route)
```

Composition happens in exactly one function. Every consumer above it sees a uniform tuple and never knows which store a row came from.

`AwardLink` is the one non-obvious piece. `plan_affiliation_countries` and `plan_subject_affiliations` currently reach through the record to read `affiliation_city` while already inside a named institution's group (`:866-873`, `:905-908`). Once a record has two affiliations, "the record's city" is ambiguous — the code needs the specific row that placed this award under this institution.

## `website/build.py`

Add beside the existing dataclasses near `:181-204`:

```python
@dataclass(frozen=True, slots=True)
class AwardAffiliation:
    """One recorded affiliation of one award. `position` orders rows; it does not rank them."""
    position: int
    name: str
    sub_name: str
    city: str
    country: str
    coordinates: str
    wikidata_qid: str


@dataclass(frozen=True, slots=True)
class AwardLink:
    """An award as it appears under one institution, carrying the affiliation row that placed it there."""
    record: "AwardRecord"
    affiliation: AwardAffiliation
    route: str
```

| Site | Line(s) | Change |
|---|---|---|
| `AWARD_COLUMNS` | `:119-124` | Unchanged — the flat columns are still selected; they are position 1. |
| `AwardRecord` | `:168-173` | Keep the six scalar fields (they feed composition), append `affiliations: tuple[AwardAffiliation, ...] = ()` as the **last** field. |
| `Affiliation.awards` | `:202` | Retype `tuple[tuple[AwardRecord, str], ...]` → `tuple[AwardLink, ...]`. |
| `read_database` | `:583-641` | Add a `SELECT … FROM award_extra_affiliations ORDER BY award_record_id, position`; at `:640` compose position 1 from the flat fields (skip if all six are blank) plus the extras, into `affiliations=`. |
| `explorer_payload` | `:408-410` | Loop `record.affiliations`. **Easy to miss — the build fails without it.** |
| `map_payload` | `:512-529` | Loop affiliations, emit points per row. |
| `_winner_description` | `:672-682` | Use the first affiliation with a non-blank name. |
| `_laureate_schema` | `:715-719` | Filter to non-blank names first, then single object for one, list for more. The single-object form MUST keep emitting the nested `department` from `sub_name` — 277 rows have one. |
| `plan_places` | `:783-786`, `:800-804`, `:821-832` | Build `AwardLink`s; blocklist and `_nonblank` guards apply per affiliation row. Keep the `BuildFailure` at `:834-835`. |
| `plan_affiliation_countries` | `:866-873` | Read `link.affiliation.country` / `.city`. |
| `plan_subject_affiliations` | `:905-908` | Same. |
| `_place_label` | `:917-920` | Signature takes `AwardAffiliation`. |
| Winner page context | `:1313-1317` | `affiliation_route` becomes `affiliation_routes`, one per affiliation, blocklist per row. |
| Affiliation page loop | **`:1499-1500`** | `_year_span([...for record, _ in affiliation.awards])` unpacks the old 2-tuple. Missed by an earlier draft of this spec; it breaks the build. |
| `recorded_affiliations` | `:1415` | MUST stay **per-award** (`any(...)`), not a row count — it renders as "recorded for N of M awards". |
| `recorded_affiliation_countries` | `:1444` | Same. |

`AFFILIATION_BLOCKLIST` (`:84`) applies per affiliation row at `:783`, `:802`, `:1315`.

## Retire the `;` convention for affiliations

Positions replace it, and production has zero rows using it in any affiliation column.

- `explorer_payload:408` and `plan_affiliation_countries:867` — drop the `.split(";")`.
- `map_payload:512-527` — call `parse_map_points` with `multiple=False`; delete the "Multiple recorded institutions" branch. `parse_map_points`'s `multiple` parameter (`:450`) MAY remain if another caller needs it.
- Six fixtures encode `;` in `affiliation_country`: `tests/test_build_website.py:126`, `:139`, `:242`, `:769`, `:780`, `:802`. Rewrite them as multiple affiliations.

**`citizenship_countries` keeps `;`** — 460 live rows use it (`build.py:411`) and it is genuinely multi-valued on one award.

## `scripts/validate_awards.py`

Eight of the nine checks read affiliation columns; only `laureate-two-names` (`:58-66`) does not. Each MUST see both stores, via one shared CTE rather than eight ad-hoc unions:

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

Checks to repoint: `coords-without-qid` `:33-41`, `institution-facts-disagree` `:42-57`, `coords-shared-across-cities` `:67-78`, `umbrella-qid` `:79-89`, `sub-name-is-the-institution` `:90-99`, `city-with-state-suffix` `:101-107`, `affiliation-without-qid` `:109-116`, `missing-place` `:118-124`.

`institution-facts-disagree` is the control on this design's one hazard: a second affiliation typed with a different city than the same institution's position-1 rows. It MUST cover the CTE, not just `awards`.

There is **no `--all` flag** — bare invocation runs every check. Do not write `validate_awards.py --all` in any runbook.

## Loading — `scripts/load_extra_affiliations.py`

New file. Creates the table if absent, then loads a reviewed TSV keyed by `award_record_id`, assigning positions from 2 upward in file order. It MUST back up the database first, refuse rows whose `award_record_id` is not in `awards`, and log the counts it wrote.

The input TSV MUST be committed under `datasets/`. The prior session's extractor produced 62 clean matches into a scratchpad file that was never committed; that file is the starting point, and only hand-reviewed rows go in (Assumption 2).

Once this lands, adding affiliations is a **data** operation — load more rows, rebuild. No further code change.

## Verification

```
1. baseline    build the site from the working tree, then: mv website/dist dist.before
               (build.py has no --output flag; it always promotes to website/dist)
2. schema      uv run scripts/load_extra_affiliations.py --dry-run   → row counts, no writes
3. load        uv run scripts/load_extra_affiliations.py
4. gate A      uv run scripts/validate_awards.py    → no new fatal failures
5. gate B      uv run pytest tests/ ; uv run ruff check
6. gate C      diff -r dist.before/ website/dist/   → every changed page traces to a loaded row
```

Gate C is a reviewed delta, not an empty diff. A page that changed without a corresponding loaded affiliation means composition is wrong.

The baseline MUST be built from the working tree as it stands. A `git checkout` of HEAD does not reproduce it — `awards.sqlite3` has uncommitted data fixes and `validate_awards.py` is untracked.

### Requirement: composition is order-stable and complete — MUST

#### Scenario: an award with one flat affiliation and one extra
- WHEN the record is composed
- THEN `record.affiliations` has length 2, positions 1 and 2 in that order
- AND the award appears under both institutions on `/affiliations/`
- AND each institution's page shows its own city, not the other's

#### Scenario: an award with no affiliation at all
- WHEN all six flat values are blank and no extra row exists
- THEN `record.affiliations` is empty and no affiliation section renders

## Risks

- **Position 1 is physically special.** It lives in different storage from 2+, so direct SQL must union the two (hence the CTE). Above `read_database()` the asymmetry is invisible. Collapsing both into one table later is mechanical and is not needed to ship this.
- **A second affiliation can disagree with its institution's other rows** on city or coordinates. `institution-facts-disagree` over the CTE is the only control.
- **Pre-existing and untouched:** `The Ohio State University` carries both `Columbus` and `Columbus, OH`; 347 rows use the `City, ST` form against a 2236-row bare-city house style.
