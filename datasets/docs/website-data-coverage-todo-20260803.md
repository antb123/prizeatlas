# TODO — What's missing data coverage — 20260803

Spec: `datasets/docs/website-data-coverage-20260803.md`. Read its **Assumptions** block plus your own task block; you
should not need the rest.

All paths are relative to the repo root. Run every command from `/home/antb2/dev/rsync/prizeatlas`.

Test command for every verify step:

```
uv run --with pytest --with pillow --with jinja2 python -m pytest datasets/tests/test_build_website.py -q
```

Baseline before any change: **60 passed, 21 subtests passed**. A task is not done until that number is met or
exceeded and no test fails.

```
T1 ──┐
T2 ──┼──► T3 ──► T5
T4 ──┘
```

T1, T2 and T4 touch disjoint files and run in parallel. T3 needs both T1 (context keys) and T2 (catalogue keys) or the
build fails. T5 is last.

---

## T1 — build.py: Coverage type, builders, wiring, localisation

**Depends-on:** none. **Files:** `datasets/website/build.py` only. Serial owner of this file.

### Steps

1. After the `Affiliation` dataclass (ends `datasets/website/build.py:423`) add:

```python
@dataclass(frozen=True, slots=True)
class Coverage:
    """One field's completeness. `total` is the rows the field can apply to, which is not always every row."""
    label_key: str
    recorded: int
    total: int

    @property
    def missing(self) -> int:
        return self.total - self.recorded

    @property
    def percent(self) -> float:
        return self.recorded / self.total * 100 if self.total else 0.0
```

2. Immediately before `def plan_about_page(` (`datasets/website/build.py:3432`) add `_located`, `_award_coverage` and
   `_institution_coverage` exactly as written in the spec's **Builders** section. Three points that are easy to get
   wrong:
   - `_award_coverage` uses `_named_affiliations(record)` for the institution rows, **never**
     `record.affiliation_name` (Assumption 3).
   - both builders sort **ascending** by `percent` — `key=lambda item: item.percent`, no minus sign (Requirement 5).
   - `_institution_coverage` guards `p and _nonblank(p.kind)` because `Affiliation.profile` is
     `AffiliationProfile | None` (`datasets/website/build.py:420`).

3. In `plan_about_page`, add four keyword arguments to the `_page(...)` call after `totals=(...)`, which currently
   ends at `datasets/website/build.py:3459`:

```python
        award_coverage=_award_coverage(records),
        institution_coverage=_institution_coverage(affiliations),
        award_total=len(records),
        institution_total=len(affiliations),
```

   `award_total` and `institution_total` are plain `int`. Do not pre-format them and do not pass the sequences.

4. Add `_localized_coverage` (spec's **Localisation** section) as a module-level function near `format_number`
   (`datasets/website/build.py:922`).

5. In `_render_job`, directly after the existing `totals` block that ends at `datasets/website/build.py:4485`, insert:

```python
    for key in ("award_coverage", "institution_coverage"):
        if rows := context.get(key):
            context[key] = _localized_coverage(language, rows)
    for key in ("award_total", "institution_total"):
        if (value := context.get(key)) is not None:
            context[key] = format_number(value, language)
```

   This is the **only** render path — do not look for a second one. `datasets/website/build.py:4592` is
   `render_error_page` for `/404.html` and is not involved.

### Verify

- `uv run ruff check datasets/website/build.py` is clean.
- The test suite still passes at the baseline. Tests for the new behaviour arrive in T5; T1 must not regress anything.

---

## T2 — i18n: 20 new keys in four catalogues

**Depends-on:** none. **Files:** `datasets/website/i18n/en.toml`, `es.toml`, `fr.toml`, `ja.toml`.

### Steps

1. Add all 20 `coverage.*` keys from the spec's **New keys** table to `en.toml`, beside the existing `about.*` block
   (`datasets/website/i18n/en.toml:323-378`).
2. Add the same 20 keys to `es.toml`, `fr.toml` and `ja.toml` with translations. `datasets/website/build.py:846`
   requires the four catalogues to hold **identical key sets** — a key missing from one file fails the whole build.
3. Placeholders MUST match English exactly (`datasets/website/build.py:854`): `coverage.of` takes `{recorded}` and
   `{total}`; `coverage.awards_caption` and `coverage.institutions_caption` take `{total}`. Every other key takes
   none.
4. Do **not** add any new key to any catalogue's `reviewed = [...]` list. These translations have not been checked by
   a speaker.
5. Do **not** create `coverage.birth_date`, `coverage.birth_city`, `coverage.birth_country`,
   `coverage.citizenship_countries` or `coverage.how_to_apply`. Those five rows reuse existing keys.

### Verify

- `grep -c '^"coverage\.' datasets/website/i18n/en.toml` prints `20`, and the same for the other three files.
- The test suite passes; a key-set mismatch surfaces as `BuildFailure: language=… ui keys missing=…`.

---

## T3 — about.html: the section and its two tables

**Depends-on:** T1, T2. **Files:** `datasets/website/templates/about.html` only.

### Steps

1. Append the `<section>` from the spec's **Template** section after the prizes section closes
   (`datasets/website/templates/about.html:60`) and before `{% endblock %}` — it must be the last section on the page
   (Requirement 6).
2. Leave the `<dl class="totals">` block (`datasets/website/templates/about.html:9-14`) untouched.
3. Each row unpacks **four** values — `label, recorded, missing, percent` — matching `_localized_coverage`'s tuple.
   The template performs no formatting and no string concatenation.

### Verify

- The test suite passes.
- Build and grep the output:
  `grep -c 'class="coverage"' datasets/website/dist/about/index.html` prints `2`.
- `grep -c 'Coverage(' datasets/website/dist/about/index.html` prints `0`.

---

## T4 — style.css: table rules

**Depends-on:** none. **Files:** `datasets/website/static/style.css` only.

### Steps

1. Add the `.coverage` block and the `@media (max-width: 26rem)` rule from the spec's **Style** section, after the
   `.award-logo` rules that end at `datasets/website/static/style.css:295`.
2. Nothing else in this file changes. The site has no other table styling and this task does not introduce any.

### Verify

- `grep -c 'tabular-nums' datasets/website/static/style.css` prints `1`.
- `grep -c 'max-width: 26rem' datasets/website/static/style.css` prints `1`.

---

## T5 — tests

**Depends-on:** T1, T2, T3, T4. **Files:** `datasets/tests/test_build_website.py` only.

### Steps

Add assertions covering, one test each:

1. **Denominators** (Requirement 1) — build coverage from a fixture holding one `Organization` record and assert that
   record is excluded from the birth-date total.
2. **Multi-institution QID** (Requirement 1) — a record with two named affiliations, one carrying a QID, counts as
   **not** covered for `coverage.institution_qid`.
3. **Blocklist** (Requirement 1) — a record whose only affiliation name is `Freelance` counts as having no
   institution.
4. **No build failure on incomplete data** (Requirement 3) — a record with two named affiliations, one with blank
   `coordinates`, builds successfully and counts as not covered for `coverage.institution_place`. Assert both.
5. **Reused labels** (Requirement 3) — the rendered about page contains the English values of `fact.birth_date`,
   `fact.birth_country`, `fact.birth_city`, `fact.citizenship_countries` and `common.how_to_apply`.
6. **Formatting** (Requirement 2) — the rendered about page contains `of` with grouped numbers and does not contain
   `Coverage(`; assert for a multilingual build and for `language_codes=("en",)`.
7. **Sort order** (Requirement 5) — the first body row of the awards table is the ORCID row.
8. **Media query** (Requirement 4) — the built `static/style.css` contains `max-width: 26rem`.

### Verify

- All eight tests pass and the suite total is at least 68 passed.
- Then perform the manual layout check Requirement 4 requires: open the four built about pages at a 320px viewport,
  confirm no horizontal body scroll, and record the exact paths and browser in the implementation handoff. Do **not**
  report Requirement 4 as verified on the unit test alone.
