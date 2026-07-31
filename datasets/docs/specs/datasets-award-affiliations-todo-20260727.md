# award_extra_affiliations — TODO (20260727)

Execution plan for `datasets-award-affiliations-20260727.md`. Paths relative to `datasets/`.

## Goals

Add `award_extra_affiliations`, compose it with the existing flat columns into one tuple per award, and load the reviewed second affiliations — so the institution rankings stop under-counting.

## Background

The flat `affiliation_*` columns stay exactly as they are and become position 1; the new table holds positions 2+. The two are disjoint, so nothing is duplicated and no maintenance script changes. Full design in `datasets-award-affiliations-20260727.md`.

**`feat/map-mvp` is assumed dead** — branch from `main`.

## Assumptions

Read before starting any block.

1. **Position is a stable sort key, not a rank.** Position 1 living in the flat columns is storage, not primacy.
2. **Only hand-reviewed affiliations are loaded**, from a committed TSV. No prose parser.
3. **The flat columns are not dropped or rewritten.** No maintenance script changes.
4. **Unknown QIDs and locations stay blank.** Never borrow either from a same-named row.
5. **Site output will change** by exactly the reviewed additions. The gate is a reviewed delta, not an empty diff.
6. **There is no `--all` flag** on `validate_awards.py`; bare invocation runs every check.

Baselines: 3093 awards, 2766 with an affiliation name, 277 with a sub-name. HHMI has 2 distinct laureates today, Berkeley 27.

## Dependency graph

```
T1 loader ──┐
T2 build.py ─┬─ T3 templates ──┬─→ T5 load + verify
             └─ T4 tests ──────┘
T6 validator ────────────────────┘
```

T2 is the sole owner of `website/build.py`. T1 and T6 touch disjoint files and are parallel-safe with it.

**Before T6:** commit `scripts/validate_awards.py` as-is — it is untracked, so its line numbers have no baseline.

---

## T1 — loader

**Goal:** `scripts/load_extra_affiliations.py` creates the table and loads a reviewed TSV.

**Depends-on:** none. **Files:** `scripts/load_extra_affiliations.py` (new, ~50 LOC).

**Steps:**

1. Match the existing script style — `argparse`, module docstring, flat functions, exceptions propagate.
2. Schema exactly as the spec's Schema section, including `CHECK (position >= 2)`.
3. `--dry-run` reports what would be written and exits without writing. Back up the database before any real write.
4. Load a TSV keyed by `award_record_id`, assigning positions from 2 upward in file order.
5. Refuse any row whose `award_record_id` is not in `awards`; report it, do not skip silently.
6. Log one line per phase: what happened, to what, how many rows.

**Verify:** `--dry-run` on the reviewed TSV reports the expected count and writes nothing. A TSV with a bogus `award_record_id` exits non-zero.

---

## T2 — build.py composes both stores

**Goal:** one uniform `record.affiliations` tuple; every consumer iterates it.

**Depends-on:** none (T1 must have run before *verifying*). **Sole owner of `website/build.py`.**

**Files:** `website/build.py` (~70 LOC changed).

**Steps:**

1. Add `AwardAffiliation` and `AwardLink` frozen dataclasses near `:181-204`, exactly as the spec defines them.
2. `AwardRecord` `:168-173` — **keep** the six scalar fields; append `affiliations: tuple[AwardAffiliation, ...] = ()` as the **last** field. `AWARD_COLUMNS` `:119-124` is unchanged.
3. `Affiliation.awards` `:202` — retype to `tuple[AwardLink, ...]`.
4. `read_database` `:583-641` — add `SELECT … FROM award_extra_affiliations ORDER BY award_record_id, position`; at `:640` compose position 1 from the flat fields (skip when all six are blank) followed by the extras.
5. Update every consumer:
   - `explorer_payload` `:408-410` — loop `record.affiliations`. **The build fails without this.**
   - `map_payload` `:512-529` — loop affiliations, emit points per row.
   - `_winner_description` `:672-682` — first affiliation with a non-blank name.
   - `_laureate_schema` `:715-719` — filter to non-blank names first, then single object for one, list for more. **Keep the nested `department` from `sub_name`** — 277 rows have one; dropping it diffs 277 pages.
   - `plan_places` `:783-786`, `:800-804`, `:821-832` — build `AwardLink`s; blocklist and `_nonblank` per affiliation row. Keep the `BuildFailure` at `:834-835`.
   - `plan_affiliation_countries` `:866-873` — read `link.affiliation.country` / `.city`.
   - `plan_subject_affiliations` `:905-908` — same.
   - `_place_label` `:917-920` — takes an `AwardAffiliation`.
   - winner page context `:1313-1317` — `affiliation_routes`, one per affiliation.
   - **`:1499-1500`** — `_year_span([... for record, _ in affiliation.awards])` unpacks the old 2-tuple. Easy to miss; it breaks the build.
   - `recorded_affiliations` `:1415` and `recorded_affiliation_countries` `:1444` — stay **per-award** (`any(...)`), not row counts.
6. `AFFILIATION_BLOCKLIST` `:84` applies per affiliation row at `:783`, `:802`, `:1315`.
7. Retire the affiliation `;` paths: drop `.split(";")` at `:408` and `:867`; `parse_map_points(multiple=False)` at `:512-527`, deleting the "Multiple recorded institutions" branch. **Do not touch `citizenship_countries` at `:411`** — 460 live rows use `;` there.

**Verify:** `uv run ruff check` clean; the build runs to completion.

---

## T3 — templates

**Goal:** templates consume the new shapes.

**Depends-on:** T2. **Files:** `website/templates/affiliation.html:26-31`, `website/templates/winner.html:17-26` (~17 LOC).

**Steps:**

1. `affiliation.html:26` — `{% for record, route in affiliation.awards %}` → `{% for link in affiliation.awards %}`; `record.*` → `link.record.*`; `:31` `record.affiliation_sub_name` → `link.affiliation.sub_name`.
2. `winner.html:17` — guard becomes `{% if record.affiliations %}`.
3. `winner.html:18-25` — keep `<section><h2>Affiliation</h2>` outside the loop; loop `record.affiliations` zipped with `affiliation_routes` inside, emitting the same `<p>` markup per affiliation.
4. Preserve existing indentation exactly — a single-affiliation award MUST render as it does today.

**Verify:** an award with one affiliation renders byte-identically against `dist.before/`.

---

## T4 — tests

**Goal:** fixtures write the new table; multi-affiliation behaviour is proven.

**Depends-on:** T2. **Files:** `tests/test_build_website.py` (~35 LOC).

**Steps:**

1. `create_database` `:34-78` — add the `award_extra_affiliations` CREATE; accept an optional per-record list of extras and insert them from position 2.
2. **Two** `award(**values)` helpers exist — `:108-111` (explorer test) and `:218-219` (map test). **Both** splat `AWARD_COLUMNS` positionally and both must build `affiliations=`. Fixing only the first breaks the map test.
3. Rewrite the six `;` fixtures as multiple affiliations: `:126`, `:139`, `:242`, `:769`, `:780`, `:802`.
4. Add one test: an award with a flat affiliation plus one extra appears under both institutions, each page showing its own city. This is the whole point of the change.

**Verify:** `uv run pytest tests/test_build_website.py` green, including the new test.

---

## T5 — load and verify

**Goal:** the reviewed affiliations are in, and every site change is accounted for.

**Depends-on:** T1, T2, T3, T4, T6.

**Files:** the reviewed TSV, committed under `datasets/`.

**Steps:**

1. Build the baseline **from the working tree**, then `mv website/dist dist.before`. `build.py` has no `--output` flag. A `git checkout` of HEAD does not reproduce the baseline — `awards.sqlite3` has uncommitted data fixes and `validate_awards.py` is untracked.
2. Commit the reviewed TSV. Only hand-reviewed rows (Assumption 2); the prior session's 62 clean matches live in an uncommitted scratchpad file and are the starting point.
3. `uv run scripts/load_extra_affiliations.py --dry-run`, then load for real.
4. Rebuild and `diff -r dist.before/ website/dist/`.

**Verify:**
- `uv run scripts/validate_awards.py` — no new fatal failures.
- `uv run pytest tests/` green; `uv run ruff check` clean.
- Every changed page traces to a loaded affiliation. A page that changed without one means composition is wrong.
- HHMI and Berkeley laureate counts rise by exactly the number of loaded rows naming them.

---

## T6 — validator covers both stores

**Goal:** the checks see positions 1 and 2+ as one set.

**Depends-on:** none. **Commit `scripts/validate_awards.py` as-is before starting.**

**Files:** `scripts/validate_awards.py:33-124` (~25 LOC).

**Steps:**

1. Add the shared `affiliations` CTE from the spec — one `UNION ALL` of the flat columns (position 1, `COALESCE`d QID) and the extras table.
2. Repoint all eight affiliation checks at the CTE: `coords-without-qid` `:33-41`, `institution-facts-disagree` `:42-57`, `coords-shared-across-cities` `:67-78`, `umbrella-qid` `:79-89`, `sub-name-is-the-institution` `:90-99`, `city-with-state-suffix` `:101-107`, `affiliation-without-qid` `:109-116`, `missing-place` `:118-124`.
3. Do NOT modify `laureate-two-names` `:58-66`. Do not change any check's `fatal` flag or `why` text.

**Verify:** with the extras table empty, every check's group count is identical to today's. `affiliation-without-qid` reports 341. Note that `institution-facts-disagree`'s `--detail` text will show `''` where it previously showed nothing, because `GROUP_CONCAT` skips `NULL` but not `''` — group counts, the actual gate, are unaffected.

---

## Not in this plan

Institution deduplication, dropping the flat columns, and the `affiliations` metadata table. The remaining unreviewed batches — 143 `sub_name` rows, ~15 slash-joined names, ~20 institutions missing from the database — are **data** loads once this lands, not code changes.
