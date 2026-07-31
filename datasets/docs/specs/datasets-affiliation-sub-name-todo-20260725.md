# TODO — affiliation sub-name

Spec: `docs/specs/datasets-affiliation-sub-name-20260725.md`. Read the **Assumptions** block of the spec before starting any task; each block below is otherwise self-contained.

Working directory: `datasets/`. Database: `awards.sqlite3`.

**Hard ordering: T1 → T3 → T5.** The migration must land before the normalizer writes, and the normalizer must run before the site build can be verified.

```
T1 migration ──┬── T3 normalizer ──── T5 build verify
               └── T4 build.py ────── T6 templates
```

`scripts/import_sqlite.py` has been deleted — `awards.sqlite3` is the sole source of truth and there is no second schema definition to keep in sync.

---

## T1 — Migrate the live database

**Depends-on:** none.
**Files:** `awards.sqlite3` (data only, no source file).

Steps:
1. Back up first: `cp awards.sqlite3 "awards.sqlite3.$(date +%Y%m%d-%H%M%S).sub-name.bak"`
2. Apply exactly this statement — the table is `STRICT`, so `TEXT NOT NULL DEFAULT ''` is mandatory:
   ```sql
   ALTER TABLE awards ADD COLUMN affiliation_sub_name TEXT NOT NULL DEFAULT '';
   ```
3. Do NOT rebuild or recreate the table. `ALTER TABLE` appending the column last is intended.

**Verify:**
- `sqlite3 awards.sqlite3 "PRAGMA table_info(awards);" | grep affiliation_sub_name` returns one row.
- `sqlite3 awards.sqlite3 "SELECT count(*) FROM awards WHERE affiliation_sub_name <> '';"` returns `0`.
- `sqlite3 awards.sqlite3 "PRAGMA integrity_check;"` returns `ok`.

---

## T3 — Rewrite the normalizer around one table

**Depends-on:** T1.
**Files:** `scripts/normalize_affiliations.py` — `ALIASES` (24-75), `report` (90-98), `suggest` (101-122), `apply_aliases` (132-147), `main` (159-182).

This is the largest task. The spec sections **One table, not two**, **The disjointness invariant**, **sub_name naming rule**, **The unit entries**, **Explicitly not merged**, **Reporting** and **Failure paths** are all normative here — read them.

Steps:
1. Rename `ALIASES` to `AFFILIATIONS` and change its type from `dict[str, str]` to `dict[str, tuple[str, str]]`, source → `(canonical_name, sub_name)`.
2. Widen all 46 existing entries mechanically to `("<existing target>", "")`. An empty sub-name means a pure spelling alias. Preserve every existing comment (lines 22-23, 41-42, 52-54) — they carry the reasoning for individual entries.
3. Rewrite the two entries at lines 67-68 in place — do **not** delete them:
   - `"Johns Hopkins University, School of Medicine": ("Johns Hopkins University", "School of Medicine")`
   - `"Yale University, School of Medicine": ("Yale University", "School of Medicine")`
4. Add the 50 unit entries from the spec's **The unit entries** table verbatim. Two of them are the entries from step 3 — do not duplicate. Watch these three specifically:
   - Parent for the geology department is `École Normale Supérieure` (**title case**). The lowercase form does not exist in the DB; using it creates a duplicate institution.
   - `Cornell University Medical College` and `Weill Cornell Medical College` both take sub_name `Weill Cornell Medical College` (one bucket).
   - `University of Massachusetts Medical School` and `UMass Chan Medical School` both take sub_name `UMass Chan Medical School`.
5. Copy the spec's **Explicitly not merged** table into a comment block above `AFFILIATIONS`, in the style of the existing inline comments.
6. Add the module-level disjointness guard immediately after the table:
   ```python
   _targets = {name for name, _ in AFFILIATIONS.values()}
   if overlap := _targets & set(AFFILIATIONS):
       raise NormalizeFailure(f"affiliation target is also a source: {sorted(overlap)}")
   ```
7. Update `suggest()` line 108: `known = set(AFFILIATIONS) | {name for name, _ in AFFILIATIONS.values()}`.
8. Update `report()` (90-98) to unpack the tuple and report unit rows separately from alias rows. The unused-source warning at 170-172 MUST cover unit entries too.
9. Rewrite `apply_aliases()` (132-147) to write both columns in one statement per entry:
   ```sql
   UPDATE awards SET affiliation_name = ?, affiliation_sub_name = ? WHERE affiliation_name = ?
   ```
   Do **NOT** add `AND affiliation_sub_name = ''` — the column is derived and owned by this script; the guard would break idempotent repair.
10. Add a guard clause checking the column exists **before** `back_up()` (line 176), so an unmigrated DB fails cleanly instead of raising mid-transaction and leaving a junk `.bak`:
    ```
    affiliations normalize failed: column affiliation_sub_name missing, run the migration
    ```
11. Add a `compound=N` summary counter (`affiliation_name LIKE '%;%'`) to the dry-run line. Summary count only — no per-row dump.
12. Keep `--apply` opt-in and the existing `PRAGMA integrity_check`.

**Verify:**
- `uv run scripts/normalize_affiliations.py` (dry run) exits 0 and reports `unit_rows=109`.
- Dry run twice — output identical, database unchanged (`sqlite3 awards.sqlite3 "SELECT count(*) FROM awards WHERE affiliation_sub_name <> '';"` still `0`).
- `uv run scripts/normalize_affiliations.py --apply` exits 0, prints a backup path, and that backup file exists.
- `sqlite3 awards.sqlite3 "SELECT count(*) FROM awards WHERE affiliation_sub_name <> '';"` returns `109`.
- `sqlite3 awards.sqlite3 "SELECT count(DISTINCT laureate_wikidata_qid) FROM awards WHERE laureate_wikidata_qid<>'' AND affiliation_name='Harvard University';"` returns `80`.
- **Idempotence:** run `--apply` a second time; it reports `unit_rows=0` and the `109` count is unchanged.
- **Guard:** temporarily add an entry whose target is an existing key; confirm the script raises `NormalizeFailure` and exits non-zero without touching the DB. Remove the test entry.
- `sqlite3 awards.sqlite3 "SELECT count(*) FROM awards WHERE affiliation_name IN ('Massachusetts General Hospital','Brigham and Women''s Hospital','Mayo Clinic','Baylor College of Medicine') AND affiliation_sub_name <> '';"` returns `0` — non-merges untouched.
- `uv run ruff check scripts/normalize_affiliations.py` clean.

---

## T4 — Read the column and group by unit in build.py

**Depends-on:** T1.
**Files:** `website/build.py` — `AWARD_COLUMNS` (74-98), `AwardRecord` (116-141), `plan_places` (393-420), call site (785), consumer (825), JSON-LD (351-352), winner description (720-721).

Steps:
1. Add `"affiliation_sub_name"` to `AWARD_COLUMNS` and `affiliation_sub_name: str` to `AwardRecord`. Order between the two does not matter — `build.py:298` looks up by name — but **every `AwardRecord` field name must exist in `AWARD_COLUMNS`** or that lookup raises.
2. In `plan_places`, rekey `by_affiliation` (line 400) from `dict[str, set[str]]` to `dict[tuple[str, str], set[str]]` on `(affiliation_name, affiliation_sub_name)`. Build **one** structure — do not add a parallel breakdown dict.
3. Derive each parent's ranked count as the **union** of its buckets' QID sets, not the sum of their lengths. A laureate under both a school and the university proper must count once.
4. Keep the `AFFILIATION_BLOCKLIST` test at line 406 on `affiliation_name` (the parent) — no change needed.
5. Extend the return so each ranked affiliation carries its non-blank sub-buckets as `(sub_name, count)`, sorted by count descending then name. **Suppress the `''` bucket entirely.** Update the call site at 785 and the consumer at 825.
6. Winner description (720-721): where a sub-name is non-blank, `At the time: {sub_name}, {name}.` `DESCRIPTION_LIMIT` is 160 (line 59) — if adding the sub-name would truncate the motivation, drop the sub-name from the description, not the motivation.
7. JSON-LD (351-352) — `department` takes an `Organization`, not a string:
   ```python
   payload["affiliation"] = {"@type": "Organization", "name": record.affiliation_name}
   if _nonblank(record.affiliation_sub_name):
       payload["affiliation"]["department"] = {"@type": "Organization", "name": record.affiliation_sub_name}
   ```

**Verify:**
- `uv run website/build.py --base-url https://example.org/awards/` exits 0.
- Page count is within a handful of the 7,265 baseline — this change adds no routes.
- `uv run ruff check website/build.py` clean.

---

## T5 — Verify the built site

**Depends-on:** T3, T4, T6.
**Files:** none — verification only.

**Verify:**
- `/affiliations/` lists `Harvard University` once, with 80 laureates.
- `Harvard Medical School`, `Harvard School of Public Health`, `Harvard University, Lyman Laboratory` and `Harvard University, Biological Laboratories` are absent as top-level rows.
- `Harvard Medical School` appears as a child of `Harvard University` with 18 laureates.
- The deferred `Harvard …;…` compound strings DO still appear as their own rows — expected, per Assumption 5. Do not "fix" them.
- No row anywhere renders "unit not recorded".
- A Harvard Medical School laureate's winner page shows both the Medical School and Harvard University, with city **Boston** (not Cambridge) — the geo columns are deliberately not rolled up.
- `grep -c "unit not recorded" website/dist -r` returns 0.

---

## T6 — Render the unit in the templates

**Depends-on:** T4.
**Files:** `website/templates/winner.html` (15-23), `website/templates/affiliations.html` (12).

House style: base HTML tags with CSS, no component libraries. Match the existing markup density.

Steps:
1. `winner.html` lines 15-23: where `record.affiliation_sub_name` is non-blank, render it above `record.affiliation_name` so the page reads unit-then-institution. The existing city/country line at 19-21 stays exactly as-is.
2. `affiliations.html` line 12: the loop currently unpacks `{% for name, count in affiliations %}`. Update it for the shape T4 returns and render the sub-buckets as a nested list beneath each parent. Parents with no sub-buckets MUST render exactly as they do today — no empty `<ul>`, no placeholder row.

**Verify:**
- `uv run website/build.py --base-url https://example.org/awards/` exits 0.
- Rendered `/affiliations/` shows the Harvard nesting; a parent with no units (e.g. `Rockefeller University`) renders as a plain row with no empty list markup.
- No raw Jinja braces in the output.

---

## Out of scope — do not do these

- The 49 compound `;`-separated strings (Assumption 5).
- The adjacent findings in the spec: `Washington University` variants, `UT Southwestern` spellings, `Baylor University College of Medicine`, the `Harvard Medical School, Massachusetts General Hospital` → New York geocoding error, the `University of Paris` era problem. **`Washington University` in particular MUST NOT be aliased without reading §The disjointness invariant** — it is also a parent, and a naive alias splits the institution across two names.
- Restoring `scripts/import_sqlite.py` or any CSV import path.
- The 4 pre-existing `test_enrich_json` failures (`fill()` takes 5 args, `enrich.py:597` passes 6, broken by `--overwrite` in `fdc11b8`) and the `jinja2` import error in `test_build_website`. Both predate this work.
- Blanking or reconciling `affiliation_city` / `affiliation_country` / `affiliation_coordinates` on roll-up. Multi-city parents are intended.
