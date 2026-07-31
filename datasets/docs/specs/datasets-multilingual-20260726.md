# Multilingual awards website — English, Spanish, French

## Goals

Publish the awards website in English, Spanish and French from one build, with localized UI, localized URL slugs and
correct `hreflang` signalling, while leaving every existing English URL untouched and keeping the build fully offline.

## Background

`website/build.py` (1,426 lines) is a single-language static generator. Language is baked in at three levels:

1. **Route constants** — `PEOPLE_ROUTE`, `COUNTRIES_ROUTE`, `AFFILIATIONS_ROUTE`, `EXPLORER_ROUTE`
   (`website/build.py:55-60`) are module-level English literals, referenced across roughly fifteen call sites.
2. **Generated prose** — `create_site_plan()` (`website/build.py:737`) builds titles and descriptions from English
   f-strings, e.g. `"All {n} {prize} laureates in {category}"` (line 874), `"Where laureates were born"` (line 1064),
   `"The birthplaces of {n:,} laureates"` (line 1066), and inline pluralization
   `{'laureate' if len(...) == 1 else 'laureates'}` (line 1081). `Breadcrumb("Home", "/")` recurs at lines 878, 943,
   969, 997, 1049 and 1069. `FACT_FIELDS` (`website/build.py:72-82`) holds nine English field labels.
3. **Templates** — 14 files in `website/templates/` carry 59 literal UI strings; `base.html:21-30` holds the site name,
   tagline and four nav labels.

The explorer landed as a page of this site in commits `2c8142b` and `ea1dc1a`, so `website/templates/explorer.html`
adds its own English UI: dropdown options, section notes, chart tooltips built in JavaScript, and a payload whose
`countries` array holds English country names.

Content volume, measured against the live database:

| Content | Volume | Disposition |
|---|---|---|
| Template UI literals | 59 | translate |
| Generated-prose sites in `build.py` | ~25 | translate |
| Prize names | 14 | translate |
| Categories | 90 | translate |
| Country names | 92 | translate |
| Institution names | 943 | Wikidata where available, else keep original |
| Curated blurbs + reasoning | 4,844 chars | translate |
| **Award motivations** | **412,813 chars (~66,000 words)** | **keep in original language** |

Motivations are 97% of the text and are quoted official citations, so they stay in their source language and are
labelled as quotations. This is the decision that keeps the project tractable at roughly 400 translatable units.

## Assumptions

1. **(Load-bearing)** Scope is UI plus controlled vocabulary. Award motivations are **not** translated; they render as
   quoted citations under a translated label. Confirmed by the user.
2. **(Load-bearing)** English stays at the root. `/people/…` keeps its exact current URL; Spanish and French mount at
   `/es/…` and `/fr/…`. No redirects, no change to any of the 8,208 existing routes. Confirmed by the user.
3. **(Load-bearing)** Slugs are localized — `/es/personas/`, `/fr/personnes/`. Confirmed by the user. This requires a
   per-language route-segment map and means a given entity has a different path in each language, so `hreflang`
   alternates MUST be derived from a language-independent page key rather than by string-munging routes.
4. **(Load-bearing)** `slugify()` (`website/build.py:225-231`) NFKD-folds and strips to ASCII, so `Física` → `fisica`
   and `Côte` → `cote`. It needs **no change** for Spanish or French. Verified by reading the implementation.
5. **(Load-bearing)** The build MUST stay offline. `AGENTS.md` states the builder uses only static files. Both Wikidata
   labels and machine translations are produced by separate scripts into committed TOML, never during `build_site()`.
6. **(Load-bearing)** Spanish and French catalogues are **machine translated as an authoring step, not at build time**.
   `scripts/translate_catalogue.py` reads `en.toml`, translates, and writes `es.toml` / `fr.toml`, which are committed.
   The build reads only those committed files. This keeps builds offline and deterministic, makes every string a
   reviewable diff, and — critically — means a human correction to a bad translation **persists** instead of being
   overwritten on the next build. Regenerating MUST NOT clobber strings marked as human-reviewed (see
   `## Machine translation`).
7. **(Load-bearing)** Wikidata coverage is partial and was measured, not assumed: `award_wikidata_qid` covers 14/14
   prizes, but `affiliation_wikidata_qid` covers only **304 of 943** institution names (32%), and countries and
   categories have **no QID column at all**. Countries (92) and categories (90) MUST therefore be hand-authored.
   Institutions without a QID keep their original name — correct behaviour, since institution names are proper nouns.
8. A missing translation key MUST fail the build, never silently fall back to English. Half-translated pages are worse
   than a failed build and would ship invisibly. This matches the existing `StrictUndefined` (`build.py:1289`) and
   `BuildFailure` posture.
9. Personal names are never translated. Dates stay ISO `YYYY-MM-DD`, which is unambiguous across all three languages.
10. French pluralizes 0 as singular (`0 lauréat`), unlike English and Spanish. The plural helper MUST take this from
    the language, not hardcode `n == 1`.
11. **(Load-bearing)** English source strings MUST be phrased to avoid grammatical gender. Spanish and French inflect
    for it and an isolated string gives MT no way to choose: `Winner` (`website/build.py:865, 933, 964, 967`) is
    `Ganador`/`Ganadora`, `Born` (`website/build.py:74`, `templates/country.html:4`) is `Nacido`/`Nacida`. The database
    holds **227 female and 2,820 male** laureates, so a masculine default is wrong on 227 people's pages. Source
    strings therefore use noun forms — `Born` becomes a `Nacimiento` / `Naissance` style label, not a participle
    agreeing with a person.
12. Page count triples: 8,208 → **24,624**. This stays under the 50,000-URL single-sitemap limit that
    `write_sitemaps()` (`website/build.py:1233`) already guards, so sitemap sharding is not triggered — but the margin
    is now 2×, not 6×.

## Scope

**24 files** (18 modified, 6 new). The line counts below are indicative and **non-binding** — the catalogues and the
test matrix (every page family × 3 languages, plus collision, preflight, hreflang and switcher cases) will likely run
over. The file list and the acceptance criteria are the planning surface that matters.

| File | Change | Size |
|---|---|---|
| `website/build.py` | modify — `Language` model, per-language planning, prose catalogue lookups, hreflang | +260 / −110 |
| `website/i18n/en.toml` | **new** — UI + vocabulary catalogue, English, hand-authored source of truth | +230 |
| `website/i18n/es.toml` | **new** — Spanish, machine translated then committed | +230 |
| `website/i18n/fr.toml` | **new** — French, machine translated then committed | +230 |
| `website/i18n/labels.toml` | **new** — Wikidata-derived entity labels, generated, committed | +~950 |
| `scripts/fetch_wikidata_labels.py` | **new** — offline fetch of es/fr labels into `labels.toml` | +90 |
| `scripts/translate_catalogue.py` | **new** — MT `en.toml` → `es.toml`/`fr.toml`, placeholder + glossary checks | +120 |
| `website/templates/base.html` | modify — `lang` attribute, nav from catalogue, language switcher | +14 / −6 |
| `website/templates/*.html` (12 others) | modify — replace 59 literals with catalogue lookups | +~60 / −60 |
| `website/templates/explorer.html` | modify — UI strings and chart labels from catalogue | +40 / −35 |
| `website/static/style.css` | modify — language switcher styling | +18 |
| `tests/test_build_website.py` | modify — routing, catalogue, hreflang, parity tests | +120 |
| `AGENTS.md` | modify — document the multilingual build | +20 |

## Design

### Language as a value, not a global

The single structural change: language-specific values move out of module constants into a frozen `Language` passed
through planning and rendering.

```python
@dataclass(frozen=True, slots=True)
class Language:
    code: str                      # "en" | "es" | "fr"
    prefix: str                    # "" | "/es" | "/fr"
    segments: dict[str, str]       # {"people": "personas", "countries": "paises", ...}
    ui: dict[str, str]             # UI strings, flat dotted keys
    terms: dict[str, str]          # prize / category / country / institution labels

    def route(self, segment: str, *parts: str) -> str: ...   # "/es/personas/marie-curie/"
    def text(self, key: str, **fields: object) -> str: ...   # UI string — MUST exist
    def term(self, kind: str, value: str) -> str: ...        # prize/category/country — MUST exist
    def plural(self, count: int, key: str) -> str: ...       # honours Assumption 10
    def entity_label(self, qid: str, fallback: str) -> str: ...  # Wikidata — MAY fall back
```

**Two lookup contracts, deliberately separate** (they were conflated in an earlier draft):

| Method | Source | On miss |
|---|---|---|
| `text()` | hand-authored `[ui]` | **`BuildFailure`** naming key + language |
| `term()` | hand-authored `[terms.*]` — 14 prizes, 90 categories, 92 countries | **`BuildFailure`** naming term + language |
| `entity_label()` | generated `labels.toml` — institutions | **returns `fallback`** (the original name) |

The first two are closed vocabularies that a human must complete, so a miss is a bug. The third is an open set with
known 32% coverage (Assumption 7), where falling back to the recorded proper noun is the correct result, not a defect.

`PEOPLE_ROUTE` and its three siblings (`website/build.py:55-60`) are **deleted**; every reference becomes
`language.route("people", …)`.

```
BEFORE                                  AFTER
──────                                  ─────
read_database()                         load_languages()         ← preflight, fails early
      │                                       │
      │                                 read_database()          ← still one read
      │                                       │
create_site_plan(…, base_url)           for language in (EN, ES, FR):
      │                                     create_site_plan(…, language)
      └─► SitePlan(jobs)                        └─► SitePlan(jobs)   ← 3 plans
              │                                          │
              │                                 group by key → alternates
              │                                          │
      render → dist/                          merge → render → dist/
                                                    ├── people/…        (en)
                                                    ├── es/personas/…
                                                    └── fr/personnes/…
```

**Preflight.** `load_languages()` runs **before** planning and rendering, and validates every catalogue up front:
all `[segments]` keys present, every required `[ui]` key present, and a `[terms.*]` entry for each of the 14 prize
names, 90 categories and 92 countries actually present in the database. Rendering happens inside a
`ThreadPoolExecutor` (`website/build.py:1385-1390`), where a `BuildFailure` raised mid-render surfaces from a worker
thread and is far harder to read. Validating first turns every catalogue error into one clear message before any page
is built.

### Page identity and hreflang

Each `PageJob` gains two fields:

```python
key: str            # language-independent identity, e.g. "person:Q7186", "prize:Q38104/category:physics"
language: Language
```

After all three plans are built, `build_site()` groups jobs by `key` to produce `alternates: dict[str, str]`
(language code → route) and passes it to the renderer. `base.html` emits one `<link rel="alternate" hreflang="…">` per
sibling plus `x-default` pointing at English. Because `key` is derived from stable identifiers (QIDs, English slugs),
this is robust against localized slugs diverging (Assumption 3).

Key formats are fixed, one per page family, and MUST NOT embed any localized string:

| Page family | Key format |
|---|---|
| Home | `home` |
| Prize | `prize:<award_qid>` |
| Category | `category:<award_qid>:<english_category_slug>` |
| Year | `year:<award_qid>:<year>` |
| Winner | `winner:<award_record_id>` |
| Person | `person:<laureate_qid>` |
| People index / page N | `people:index` / `people:page-<n>` |
| Countries index | `countries:index` |
| Country | `country:<english_country_slug>` |
| Institutions index | `affiliations:index` |
| Institution | `affiliation:<english_affiliation_slug>` |
| Explorer | `explorer` |

Person keys are unconditionally QID-based because `person_routes()` (`website/build.py:690-712`) already **skips**
records without a `laureate_wikidata_qid` — *"a wrong merge is worse than a missing page"* (lines 693-694). There are
therefore no un-QID person pages to key, and none must be introduced. Winner pages carry the per-award identity
instead, keyed by `award_record_id`.

A page MUST have an entry for every configured language or the build fails — that check is the guard against a
localized plan silently dropping pages.

### Slug policy

"Localized slugs" (Assumption 3) applies to route **segments** and to slugs derived from translated vocabulary. It
does **not** apply to proper nouns:

| Path component | Localized? | Derived from |
|---|---|---|
| Route segment (`people` → `personas`) | **yes** | `[segments]` in the catalogue |
| Category slug (`physics` → `fisica`) | **yes** | `slugify(term("category", …))` |
| Country slug (`france` → `francia`) | **yes** | `slugify(term("country", …))` |
| Prize slug (`nobel-prize`) | **no** | `award_ranking.slug`, unchanged in all languages |
| Person slug (`marie-curie`) | **no** | `slugify(full_name)` — a personal name |
| Institution slug | **no** | `affiliation_slug(name)` — a proper noun |

Prize slugs stay canonical because `award_ranking.slug` is also the key of the logo map in `read_database()`
(`website/build.py:446-459`); localizing it would silently break logo resolution. Person and institution slugs stay
canonical per Assumption 9.

Because localized category and country slugs are newly derived, the existing duplicate-route guard MUST run per
language and its error MUST name the colliding route and language — e.g. two distinct English categories whose
Spanish translations slugify identically.

### Translation catalogue

Three hand-authored TOML files, matching the existing `award_ranking.toml` convention:

```toml
# website/i18n/es.toml
code = "es"
prefix = "/es"

[segments]
people = "personas"
countries = "paises"
affiliations = "instituciones"
explorer = "explorador"

[ui]
# Keys MUST be quoted. Bare `site.name = …` is a TOML dotted key and parses as a nested
# table, which would not match the flat lookup `language.text("site.name")`.
"site.name" = "Premios"
"site.tagline" = "Reconocimiento al trabajo de impacto duradero"
"nav.people" = "Personas"
"fact.born" = "Nacimiento"
"motivation.label" = "Mención oficial"
"countries.title" = "Dónde nacieron los laureados"
"countries.description" = "Los lugares de nacimiento de {count} laureados en {countries} países."
"people.count.one" = "{count} laureado"
"people.count.other" = "{count} laureados"

[terms.prize]
"Nobel Prize" = "Premio Nobel"

[terms.category]
"Physics" = "Física"

[terms.country]
"United States" = "Estados Unidos"

# Curated ranking copy, keyed by award_wikidata_qid. All three fields are required for every
# one of the 14 prizes; blurb and reasoning are short (4,844 chars total across all prizes).
[ranking.Q38104]
blurb = "…"
reasoning = "…"
```

`Ranking.blurb` and `Ranking.reasoning` (`website/build.py:425-429`, read from `award_ranking`) are used **only** as
the English text. For Spanish and French the renderer takes `[ranking.<qid>]` from the catalogue via `term()`
semantics — required, failing the build if absent. No database column is added.

`Language.text()` formats with `str.format`, raising `BuildFailure` naming the missing key and language
(Assumption 8). Numbers are formatted per language — English `1,234`, Spanish and French `1 234` — by a
`format_number(value, language)` helper replacing the bare `{:,}` at `website/build.py:1066` and its siblings.

### Machine translation

`scripts/translate_catalogue.py` reads `website/i18n/en.toml` — the single source of truth — and writes `es.toml` and
`fr.toml`. It runs on demand, never during a build, and its output is committed (Assumption 6).

**Placeholder integrity is the failure that will actually bite.** Catalogue strings carry `str.format` fields:

```toml
"countries.description" = "The birthplaces of {count} laureates across {countries} countries."
```

MT engines routinely translate, reorder, space, or drop such tokens — `{count}` becomes `{cuenta}`, `{ count }`, or
vanishes. A mangled field raises `KeyError` at render time, deep inside a worker thread, on one page out of 24,624.
The script MUST therefore verify, per string, that the **multiset of placeholder names in the translation is identical
to the source**, and fail loudly naming the key, the language and the diff. Reordering within the sentence is fine and
expected — Spanish and French often need it — but the set of names must match exactly.

**A glossary pins the recurring terms** so they do not drift between strings. MT will otherwise render *laureate* three
different ways across three sentences:

| English | Spanish | French |
|---|---|---|
| laureate | laureado | lauréat |
| award | premio | prix |
| prize | premio | prix |
| institution | institución | institution |

**Human corrections MUST survive regeneration.** Each entry carries a review marker; the script leaves marked strings
untouched and only rewrites unmarked ones:

```toml
"nav.people" = "Personas"          # reviewed = true → never regenerated
"fact.born" = "Nacimiento"         # unmarked      → rewritten on next run
```

Without this, the first correction someone makes is silently reverted by the next run, and the failure is invisible
until a reader notices. The script MUST report `translated=N preserved=M failed=K` on completion.

**Two things MT does not touch:** award motivations (Assumption 1 — they stay in the original language) and entity
names covered by Wikidata, whose labels are human-curated and better than MT for proper nouns.

**Quality is bounded, and that is a product decision, not a bug.** Isolated UI fragments are MT's weakest case — no
surrounding context, and the 90 category and 92 country terms are exactly where a wrong word is most visible. The
review markers exist so those can be fixed once, permanently. Recommend reviewing the ~200 highest-visibility strings
(nav, headings, the 14 prize names, the 92 countries) before launch and leaving the long tail machine-quality.

### Wikidata labels — fetched offline, committed

`scripts/fetch_wikidata_labels.py` reads the distinct `award_wikidata_qid` and `affiliation_wikidata_qid` values from
`awards.sqlite3`, queries `wbgetentities` for `es` and `fr` labels in batches of 50, and writes
`website/i18n/labels.toml`:

```toml
[Q38104]
en = "Nobel Prize"
es = "Premio Nobel"
fr = "prix Nobel"
```

The build reads only this committed file. Per Assumption 7, expect all 14 prizes and roughly 304 institutions to
resolve; institutions with no QID or no label keep their original name, which is correct for proper nouns. The script
MUST report coverage on completion — `resolved=N missing=M` — so drift is visible.

### Explorer

`website/templates/explorer.html` needs three things:

1. UI literals (dropdown options, section notes, headings) become catalogue lookups, as with every other template.
2. Strings built in JavaScript — tooltips such as `"${n} laureates per million"`, `"Organization"`, `"awards"`,
   `"partial decade"` — MUST NOT be translated inline. Instead the payload gains a `strings` object populated from the
   catalogue at build time, and the JavaScript reads `STRINGS.perMillion` etc. This keeps one JS file for all three
   languages.
3. The payload's `countries` array is localized via `terms.country` at build time, so charts label bars in the page
   language. Country **ordering** is by count and therefore unaffected.

The `api.country.is` geo-IP lookup added in `ea1dc1a` is untouched; only its surrounding labels are translated.

## Behavior / Acceptance

### Requirement: Existing English URLs MUST NOT change

#### Scenario: root-language stability
- WHEN the multilingual build completes
- THEN every route present in the pre-change `dist/` still exists at the identical path
- AND `dist/people/index.html`, `dist/countries/index.html` and `dist/explorer/index.html` are present
- AND no English page path contains `/en/`

### Requirement: Each language MUST be complete

#### Scenario: no partial translation ships
- WHEN any required `[ui]` key or `[terms.*]` entry is missing in any language
- THEN `load_languages()` fails with a `BuildFailure` naming the key and the language
- AND it fails during preflight, before any page is planned or rendered
- AND no output is promoted to `dist/` (the staging directory is discarded)

#### Scenario: optional entity labels fall back instead of failing
- WHEN an institution has no QID, or its QID has no label for the target language
- THEN the build succeeds and the institution renders under its recorded name
- AND this is true for roughly 639 of 943 institutions (Assumption 7)

#### Scenario: page parity across languages
- WHEN the three plans are merged
- THEN every page key exists in all three languages
- AND the total page count is 3 × the single-language count

### Requirement: hreflang MUST be correct and reciprocal

#### Scenario: alternates on a localized page
- WHEN `/es/personas/marie-curie/` renders
- THEN it carries `hreflang` alternates for `en`, `es`, `fr` and `x-default`
- AND the `en` alternate resolves to `/people/marie-curie/`
- AND that English page in turn lists `/es/personas/marie-curie/` as its `es` alternate

### Requirement: Machine translation MUST preserve format placeholders

#### Scenario: mangled placeholder is caught at translation time
- WHEN a translated string's placeholder names differ from the English source in any way — renamed, spaced, dropped or
  added
- THEN `scripts/translate_catalogue.py` fails naming the key, the language, and the differing placeholders
- AND no catalogue file is written

#### Scenario: reordering is permitted
- WHEN a translation reorders placeholders within the sentence but uses the identical set of names
- THEN it is accepted, because Spanish and French word order legitimately differs from English

#### Scenario: human corrections survive regeneration
- WHEN a string is marked reviewed and the translation script is re-run
- THEN that string is left byte-identical
- AND the script reports how many strings it preserved versus rewrote

### Requirement: The language switcher MUST keep the visitor on the same page

#### Scenario: switching language mid-site
- WHEN a visitor on `/es/personas/marie-curie/` uses the language switcher to pick French
- THEN they land on `/fr/personnes/marie-curie/`, not the French home page
- AND the switcher is built from the same `alternates` map that produces `hreflang`, not from a separate list

#### Scenario: route collision from translated vocabulary
- WHEN two distinct categories or countries translate to strings that slugify identically in one language
- THEN the build fails naming the colliding route and the language

### Requirement: Localized routing MUST produce native paths

#### Scenario: segment and slug localization
- WHEN Spanish pages render
- THEN person pages live under `/es/personas/`, countries under `/es/paises/`
- AND accented slugs are ASCII-folded — a Spanish category `Física` yields `fisica`

### Requirement: Motivations MUST remain in their original language

#### Scenario: citation integrity
- WHEN a winner page renders in Spanish or French
- THEN the motivation text is byte-identical to the English page's motivation
- AND it is introduced by the translated label from `ui.motivation.label`

## Out of scope

- Translating award motivations, biographical notes, or personal names (Assumption 1, 9).
- Localized date formatting — dates stay ISO (Assumption 9).
- Any change to `awards.sqlite3` or its schema. No language columns are added; translations live in TOML.
- Language auto-detection or redirects. Language is chosen by URL and the switcher in the header.
- Professional human translation. Catalogues are machine translated with a review-marker mechanism for corrections
  (Assumption 6); a full human pass can be layered on later without any code change, by marking strings reviewed.
- Right-to-left support, and any fourth language. The `Language` model admits more, but only en/es/fr are configured.
