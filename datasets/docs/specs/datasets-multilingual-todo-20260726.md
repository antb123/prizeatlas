# TODO — Multilingual awards website (en/es/fr)

Execution plan for `docs/specs/datasets-multilingual-20260726.md`. Each block is self-contained: a sub-agent runs one block
plus the spec's **Assumptions** section, with no other context.

Read the Assumptions block before starting any task. The load-bearing ones are 1 (motivations are never translated),
2 (English stays at the root), 3 (localized slugs), 5 (the build MUST stay offline), 6 (MT is an authoring step, not a
build step), 7 (Wikidata covers 14/14 prizes but only 304/943 institutions) and 11 (English source strings MUST avoid
grammatical gender).

**Verification commands used throughout** — the suite is `unittest`, *not* pytest, which is not installed:

```
uv run python -m unittest tests/test_build_website.py     # baseline: 18 tests passing
ruff check <file>
uv run website/build.py --base-url https://example.org/awards/
```

```
T1 (en.toml) ──┬── T3 (translate script) ── T4 (es/fr.toml) ──┐
               │                                              │
               └── T5 (build.py) ──┬── T6  (base.html)        │
                                   ├── T7  (12 templates)     ├── T10 (tests) ── T12 (gate)
                                   ├── T8  (explorer.html)    │
                                   └──────────────────────────┘
T2 (wikidata labels) ─────────────────────────────────────────┤
T9 (style.css) ───────────────────────────────────────────────┤
T11 (AGENTS.md) ──────────────────────────────────────────────┘
```

**T1 and T5 are the two serial bottlenecks.** T1 gates all translation work; T5 is the sole owner of `website/build.py`
and gates every template task.

---

## T1 — Author the English catalogue, `website/i18n/en.toml`

**Depends-on:** none. **Serial — gates T3 and T5.**

**Files:** `website/i18n/en.toml` (new)

**Why first:** every other language is machine translated *from* this file, so a gendered or malformed English string
propagates into both target languages and is expensive to unwind later.

**Steps:**

1. Create `website/i18n/` and `en.toml` with four sections: `code`, `prefix`, `[segments]`, `[ui]`, `[terms.*]`,
   `[ranking.*]`.
2. `code = "en"`, `prefix = ""` (English is at the root — Assumption 2).
3. `[segments]` — the four route segments: `people`, `countries`, `affiliations`, `explorer`. English values are the
   current literals from `website/build.py:55-60`: `people`, `countries`, `affiliations`, `explorer`.
4. `[ui]` — **all keys MUST be quoted strings**, e.g. `"site.name" = "Awards"`. A bare `site.name = …` is a TOML
   dotted key and parses as a nested table, which will not match the flat `language.text("site.name")` lookup.
   Populate from:
   - `website/templates/base.html:21-30` — site name, tagline, four nav labels.
   - The 59 literal UI strings across the other 13 templates in `website/templates/`.
   - `FACT_FIELDS` (`website/build.py:72-82`) — nine field labels.
   - The generated-prose sites in `create_site_plan()`: lines 874, 940, 1064, 1066, 1081, and the `Breadcrumb("Home",
     "/")` label recurring at 878, 943, 969, 997, 1049, 1069.
   - Plural pairs as `<key>.one` / `<key>.other`.
5. **Gender-neutral phrasing is mandatory (Assumption 11).** Spanish and French inflect for gender and MT cannot
   choose correctly from an isolated string. The database holds 227 female and 2,820 male laureates, so a masculine
   default is wrong on 227 people's pages. Rewrite person-agreeing participles as nouns:
   - `Born` → a birth-date *label* (`Birth`), not a participle → `Nacimiento` / `Naissance`, never `Nacido`/`Nacida`.
   - `Died` → `Death`. `Winner` (lines 865, 933, 964, 967) → `Recipient` or an equivalent non-inflecting noun.
   - Audit every `[ui]` value for an adjective or participle that would agree with a person.
6. `[terms.prize]`, `[terms.category]`, `[terms.country]` — identity mappings for English (`"Physics" = "Physics"`).
   Source the exact strings from the database so they match at lookup time:
   `sqlite3 awards.sqlite3 "SELECT DISTINCT prize_name FROM awards;"` (14), `… category … WHERE category<>''` (90),
   `… birth_country … WHERE birth_country<>''` (92). Countries and categories have **no QID column**, so these are
   hand-authored in every language (Assumption 7).
7. `[ranking.<award_wikidata_qid>]` — `blurb` and `reasoning` per prize, copied from the `award_ranking` table for
   English. 14 entries, 4,844 chars total.

**Verify:**
- `uv run python -c` is not permitted; validate by parsing in a test added in T10, or with
  `jq -e . <(…)` equivalent — simplest is: the file loads under `tomllib` in T10's catalogue test.
- Every `[ui]` key is a quoted string: `grep -c '^[a-z]' website/i18n/en.toml` → `0` inside the `[ui]` block.
- `[terms.prize]` has 14 entries, `[terms.category]` 90, `[terms.country]` 92, `[ranking.*]` 14 tables.
- No `[ui]` value contains a gendered participle — reviewed by hand against step 5.

---

## T2 — Fetch Wikidata labels, `scripts/fetch_wikidata_labels.py`

**Depends-on:** none. **Parallel-safe.**

**Files:** `scripts/fetch_wikidata_labels.py` (new), `website/i18n/labels.toml` (new, generated then committed)

**Steps:**

1. Write the script to read distinct `award_wikidata_qid` and `affiliation_wikidata_qid` from `awards.sqlite3`
   (read-only, `?mode=ro` as `read_database()` does at `website/build.py:420`).
2. Query the Wikidata `wbgetentities` API in batches of 50 QIDs, requesting `labels` for `en`, `es`, `fr`.
3. Write `website/i18n/labels.toml` as one table per QID:
   ```toml
   [Q38104]
   en = "Nobel Prize"
   es = "Premio Nobel"
   fr = "prix Nobel"
   ```
4. Print coverage on completion: `resolved=N missing=M`, so drift is visible.
5. Run it once and commit the generated `labels.toml`. **The build never calls this script** (Assumption 5).

**Verify:**
- `ruff check scripts/fetch_wikidata_labels.py` → clean.
- All 14 prize QIDs resolve. Institution coverage is expected around 304 of 943 distinct names (Assumption 7) — a
  lower number is a finding to report, not a failure.
- `website/i18n/labels.toml` parses as TOML and is committed.

---

## T3 — Translation script, `scripts/translate_catalogue.py`

**Depends-on:** T1. **Parallel-safe** once T1 lands.

**Files:** `scripts/translate_catalogue.py` (new)

**Steps:**

1. Read `website/i18n/en.toml`, write `website/i18n/es.toml` and `fr.toml`. Runs on demand only — never during a
   build (Assumption 6).
2. **Placeholder integrity check — the critical one.** Catalogue values carry `str.format` fields such as
   `"The birthplaces of {count} laureates across {countries} countries."` MT engines rename, space, or drop these
   (`{count}` → `{cuenta}` → `KeyError` at render, inside a worker thread, on one page in 24,624). For every string,
   compare the **multiset of placeholder names** in source and translation. On any difference, fail naming the key,
   the language and the differing placeholders, and write **no** output file. Reordering placeholders within the
   sentence MUST be accepted — Spanish and French word order legitimately differs.
3. **Glossary** — pin recurring terms so they do not drift between strings:
   `laureate` → `laureado`/`lauréat`, `award` → `premio`/`prix`, `prize` → `premio`/`prix`,
   `institution` → `institución`/`institution`. Apply as a pre/post-processing termbase.
4. **Review markers** — each entry may be marked reviewed. Marked strings are left **byte-identical** on regeneration;
   only unmarked strings are rewritten. Without this the first human correction is silently reverted by the next run.
5. Report `translated=N preserved=M failed=K` on completion.
6. Do not translate: `[ranking.*]` blurbs are translated, but award **motivations** never enter the catalogue at all
   (Assumption 1) — they are read from the database and rendered as-is.

**Verify:**
- `ruff check scripts/translate_catalogue.py` → clean.
- Unit-tested in T10: a string whose translation drops a placeholder MUST raise; a string whose translation reorders
  placeholders MUST pass; a reviewed string MUST survive regeneration byte-identical.

---

## T4 — Generate and commit `es.toml` and `fr.toml`

**Depends-on:** T3. **Serial.**

**Files:** `website/i18n/es.toml` (new), `website/i18n/fr.toml` (new)

**Steps:**

1. Run `scripts/translate_catalogue.py` for both languages.
2. Set `prefix = "/es"` and `prefix = "/fr"`; translate `[segments]` to `personas`/`paises`/`instituciones`/
   `explorador` and `personnes`/`pays`/`institutions`/`explorateur`.
3. Review and mark the ~200 highest-visibility strings: nav labels, page headings, the 14 prize names, the 92 country
   names. These are where a wrong word is most visible. Leave the long tail machine-quality.
4. Check French plural handling: French uses the singular for 0 (`0 lauréat`), unlike English and Spanish
   (Assumption 10). Ensure `<key>.one` / `<key>.other` values suit that rule.
5. Commit both files.

**Verify:**
- Both files parse as TOML and carry every key present in `en.toml` — no missing keys, checked in T10.
- Placeholder check passed for every string (T3 step 2 would have failed the run otherwise).
- `[segments]` values differ from English in both files.

---

## T5 — `Language` model, routing, keys and hreflang in `website/build.py`

**Depends-on:** T1. **Serial — sole owner of `website/build.py`. Gates T6, T7, T8.**

**Files:** `website/build.py`

**Steps:**

1. Add a frozen `Language` dataclass with `code`, `prefix`, `segments`, `ui`, `terms`, and methods:
   - `route(segment, *parts) -> str` — `/es/personas/marie-curie/`
   - `text(key, **fields) -> str` — hand-authored `[ui]`; **raises `BuildFailure`** on miss
   - `term(kind, value) -> str` — `[terms.*]`; **raises `BuildFailure`** on miss
   - `plural(count, key) -> str` — honours French 0-is-singular (Assumption 10)
   - `entity_label(qid, fallback) -> str` — `labels.toml`; **returns `fallback`** on miss
   These are two deliberately different contracts: closed vocabularies fail, the open institution set falls back.
2. Add `load_languages(website_dir) -> tuple[Language, ...]` performing **preflight validation before any planning or
   rendering**: all `[segments]` keys present, every required `[ui]` key present, and a `[terms.*]` entry for each
   prize/category/country actually present in the database. Rendering runs in a `ThreadPoolExecutor`
   (`website/build.py:1385-1390`), where a mid-render `BuildFailure` surfaces from a worker thread and is far harder
   to diagnose.
3. **Delete** `PEOPLE_ROUTE`, `COUNTRIES_ROUTE`, `AFFILIATIONS_ROUTE`, `EXPLORER_ROUTE` (`website/build.py:55-60`).
   Replace every reference with `language.route(...)`. Call sites include `plan_places()` (592), `person_routes()`
   (690), `create_site_plan()` (737) throughout, and the render kwargs at 1309-1312 and 1327-1330.
4. Add `key: str` and `language: Language` to `PageJob` (`website/build.py:188`). Key formats are fixed and MUST NOT
   embed any localized string — use the table in the spec's *Page identity and hreflang* section. Person keys are
   unconditionally QID-based: `person_routes()` already skips records without a `laureate_wikidata_qid`
   (`website/build.py:690-712`, *"a wrong merge is worse than a missing page"*), so there are no un-QID person pages
   and none may be introduced.
5. Apply the slug policy from the spec: route segments, category slugs and country slugs are localized; prize, person
   and institution slugs are **not**. Prize slugs stay `award_ranking.slug` because that value is also the key of the
   logo map in `read_database()` (`website/build.py:446-459`) — localizing it silently breaks logo resolution.
6. Run the existing duplicate-route guard (`website/build.py` route uniqueness check) **per language**, and include
   the colliding route *and* the language in the error. Localized category/country slugs are newly derived and can
   collide where English did not.
7. Replace bare `{:,}` number formatting (e.g. `website/build.py:1066`) with `format_number(value, language)` —
   English `1,234`, Spanish and French `1 234`.
8. Change `create_site_plan()` (737) to take `language`, and `build_site()` (1374) to loop the languages, merge the
   three job lists, and group by `key` to build `alternates: dict[str, str]` (language code → route). Pass
   `alternates` and `lang` into `_render_job()` (1296).
9. A page MUST have an entry for every configured language, or the build fails — this is the guard against a
   localized plan silently dropping pages.

**Verify:**
- `ruff check website/build.py` → clean.
- `grep -c 'PEOPLE_ROUTE\|COUNTRIES_ROUTE\|AFFILIATIONS_ROUTE\|EXPLORER_ROUTE' website/build.py` → `0`.
- Full verification is T12; this task's own gate is ruff plus the T10 tests.

---

## T6 — `base.html`: lang attribute, nav, switcher, hreflang

**Depends-on:** T5. **Parallel-safe** with T7, T8 (distinct files).

**Files:** `website/templates/base.html`

**Steps:**
1. `<html lang="{{ lang }}">` (line 2).
2. Replace the site name, tagline and four nav labels (lines 21-30) with `text()` lookups.
3. Emit `<link rel="alternate" hreflang="…">` for each entry in `alternates`, plus `x-default` pointing at English.
4. Add a language switcher built **from the same `alternates` map** — switching language MUST keep the visitor on the
   equivalent page (`/es/personas/marie-curie/` → `/fr/personnes/marie-curie/`), never the language home page.

**Verify:** covered by T12; `404.html` must still render, since it shares this base and uses `render_error_page()`
(`website/build.py:1321`).

---

## T7 — The other 12 templates

**Depends-on:** T5. **Parallel-safe** with T6, T8.

**Files:** `website/templates/` — `index.html`, `prize.html`, `category.html`, `year.html`, `winner.html`,
`person.html`, `people.html`, `countries.html`, `country.html`, `affiliations.html`, `affiliation.html`, `404.html`

**Steps:**
1. Replace all 59 literal UI strings with `text()` lookups against keys authored in T1.
2. Leave award motivations untouched — they render from the database in their original language, introduced by the
   translated `"motivation.label"` (Assumption 1).

**Verify:** no bare English sentence remains in any template — spot-check with
`grep -n '>[A-Z][a-z]\{3,\}' website/templates/*.html`, allowing only Jinja expressions and attribute values.

---

## T8 — `explorer.html`

**Depends-on:** T5. **Parallel-safe** with T6, T7.

**Files:** `website/templates/explorer.html`

**Steps:**
1. Replace UI literals — dropdown options, section notes, headings — with `text()` lookups.
2. Strings built in JavaScript (tooltips such as `"${n} laureates per million"`, `"Organization"`, `"awards"`,
   `"partial decade"`) MUST NOT be translated inline. Add a `strings` object to the payload, populated from the
   catalogue at build time, and have the JS read `STRINGS.perMillion` and friends. One JS file serves all three
   languages.
3. Localize the payload's `countries` array via `term("country", …)` so chart bars label in the page language.
   Ordering is by count and therefore unaffected.
4. Leave the `api.country.is` geo-IP lookup alone; translate only its surrounding labels.

**Verify:** the built explorer page's JSON payload parses; extract the page script and run `node --check` → clean.

---

## T9 — Language switcher styling

**Depends-on:** none. **Parallel-safe.**

**Files:** `website/static/style.css`

**Steps:**
1. Style the switcher added in T6, matching the existing header treatment.
2. Respect the existing light/dark variables at `website/static/style.css:1-23` — use `var(--ink)`, `var(--muted)`,
   `var(--rule)`; do **not** introduce new `:root` variables.

**Verify:** the switcher is legible in both colour schemes.

---

## T10 — Tests

**Depends-on:** T4, T5. **Files:** `tests/test_build_website.py`

**Steps:**
1. Catalogue: all three files parse; `es.toml` and `fr.toml` carry every key present in `en.toml`; `[terms.*]` covers
   every prize/category/country present in the database.
2. Preflight: a catalogue missing a required key raises `BuildFailure` naming key and language, **before** any page is
   planned.
3. Fallback: an institution with no QID, or a QID with no label, renders under its recorded name without failing.
4. Placeholder integrity: a translation that drops a placeholder raises; one that reorders placeholders passes; a
   reviewed string survives regeneration byte-identical.
5. Routing: Spanish person pages live under `/es/personas/`; English pages contain no `/en/`; an accented category
   such as `Física` slugifies to `fisica`.
6. Collisions: two categories translating to the same slug in one language fail, with route and language named.
7. hreflang reciprocity: `/es/personas/marie-curie/` lists `/people/marie-curie/` as its `en` alternate, and that
   English page lists the Spanish route as its `es` alternate.
8. Parity: every page key exists in all three languages; total page count is 3× the single-language count.
9. Motivation integrity: a winner page's motivation text is byte-identical across all three languages.

**Verify:** `uv run python -m unittest tests/test_build_website.py` → all pass. Baseline is 18 tests; this task adds
to that count.

---

## T11 — Update `AGENTS.md`

**Depends-on:** none. **Parallel-safe.**

**Files:** `AGENTS.md`

**Steps:**
1. Document the multilingual build under the static-website section: three languages, English at the root, `/es/` and
   `/fr/` prefixes, localized segments and category/country slugs.
2. Document that catalogues live in `website/i18n/`, that `en.toml` is the hand-authored source of truth, and that
   `es.toml`/`fr.toml` are machine translated by `scripts/translate_catalogue.py` and committed.
3. State plainly that **the build is offline** — neither `scripts/fetch_wikidata_labels.py` nor
   `scripts/translate_catalogue.py` runs during `website/build.py`.
4. Note that award motivations are never translated.

**Verify:** `AGENTS.md` names no command that does not exist, and describes the offline-build guarantee.

---

## T12 — Full build and final gate

**Depends-on:** T1-T11. **Serial — final gate.**

**Files:** none modified; this task verifies.

**Steps:**
1. `uv run website/build.py --base-url https://example.org/awards/`.
2. Confirm every check below. On any failure, stop and report — do not paper over it.

**Verify:**
- **English URLs unchanged:** every route present in the pre-change `dist/` still exists at the identical path;
  `dist/people/index.html`, `dist/countries/index.html`, `dist/explorer/index.html` all present; no English page path
  contains `/en/`.
- **Page count:** 3 × the single-language count (8,208 → **24,624**).
- **Sitemap:** contains all three languages and stays under the 50,000-URL single-file limit that `write_sitemaps()`
  (`website/build.py:1233`) guards — 24,624 is within it, but the margin is now 2×.
- **hreflang:** reciprocal between every language pair, with `x-default` on English.
- **Switcher:** from `/es/personas/marie-curie/`, choosing French lands on `/fr/personnes/marie-curie/`.
- **Motivations:** byte-identical across all three languages for the same award record.
- **404:** `dist/404.html` renders without an undefined-variable error under `StrictUndefined`.
- **Offline:** the build makes no network request — neither label fetching nor translation runs during it.
- `uv run python -m unittest tests/test_build_website.py` → all pass.
- `ruff check website/build.py scripts/fetch_wikidata_labels.py scripts/translate_catalogue.py` → clean.
