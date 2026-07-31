# Multilingual PrizeAtlas — English, Spanish, and French

## Goals

PrizeAtlas MUST publish equivalent English, Spanish, and French static pages from one deterministic build, with localized user-facing copy, controlled vocabulary, semantic route segments, metadata, and navigation while preserving every existing English URL.

Success means that every generated English `PageJob` has reciprocal Spanish and French siblings, the build remains offline and deterministic, award citations and other source prose remain unchanged, and focused tests prove route parity, catalogue completeness, placeholder safety, localized browser-side UI, and English URL stability.

## Background

`datasets/website/build.py:38-3224` is now a 3,228-line, English-only static generator. The earlier draft described a 1,426-line generator with four route constants and 14 templates; the current code has 12 semantic route constants, nested route segments, 29 loaded templates, browser-generated UI in three large templates, JSON-LD, social images, CSV export, `llms.txt`, a 404 page, and a home-only build path.

A verified build on 2026-07-31 generated 7,345 page jobs: 16 prize families, 25 routed category pages, 1,706 year pages, 2,721 winner pages, 1,986 merged person pages, 72 birth-country pages, and 6 subject families. Three-language parity therefore produces 22,035 page jobs at the current snapshot, below the existing 50,000-URL single-sitemap limit.

Current live vocabulary and source-text measurements are:

| Content | Current volume | Translation disposition |
|---|---:|---|
| Prize names | 16 | catalogue term |
| Nonblank award categories | 86 | catalogue term |
| Countries rendered across birth, death, citizenship, and award affiliations | 87 | catalogue term |
| School subjects | 6 live values; 10 configured map-route values | catalogue term for all 10 |
| Institution names | 629 names; 574 distinct nonblank QIDs | Wikidata label when available, otherwise recorded name |
| Rendered ranking blurbs | 16 rows; 4,562 characters | catalogue copy |
| About-page editorial copy | 170 lines; 9,630 bytes | catalogue copy |
| Institution profile descriptions | 302 values; 18,346 characters | preserve as source data |
| Award motivations | 2,721 values; 362,608 characters | preserve byte-for-byte |

English is embedded in route constants at `datasets/website/build.py:79-108`, fact labels at `datasets/website/build.py:136-152`, page titles/descriptions/breadcrumbs throughout `datasets/website/build.py:954-2704`, machine-reader prose at `datasets/website/build.py:2775-2875`, share-image text at `datasets/website/build.py:2954-3045`, render globals at `datasets/website/build.py:3048-3136`, and all loaded templates. The Explorer, map, and nearby pages also construct visible strings and accessibility text in JavaScript.

## Assumptions

1. **Load-bearing:** English remains at the root; Spanish uses `/es/` and French uses `/fr/`, with no `/en/` routes or redirects.
2. **Load-bearing:** Every semantic route segment and every category, country, and subject slug is localized; prize, person, institution, year, and award-recipient slug components remain canonical.
3. **Load-bearing:** Award motivations, biographical notes, institution profile descriptions, personal names, constituent-unit names, and city names remain in their recorded source form.
4. **Load-bearing:** The website build remains offline; label fetching and machine translation are explicit authoring commands whose committed outputs are the build inputs.
5. **Load-bearing:** `datasets/website/i18n/en.toml` is the hand-authored catalogue source; committed `es.toml` and `fr.toml` are machine-translated drafts with durable human-review markers.
6. **Load-bearing:** Missing UI, route-segment, ranking, prize, category, country, subject, or laureate-type entries fail preflight; a missing institution label falls back to the recorded institution name.
7. **Load-bearing:** A language-independent page key, not route text, joins localized siblings for parity, `hreflang`, the switcher, and share assets.
8. Personal and organization identity, ranking inputs, counts, and ordering remain those of the current English planner; localization changes display labels and paths, not membership or rank.
9. Dates retain their current ISO source representation; numbers use the language's browser/server locale formatting without changing numeric values.
10. Server plural selection and browser `Intl.PluralRules` use the same language code; French therefore selects its singular form for zero and one.
11. English catalogue copy uses person-neutral nouns such as “Birth”, “Death”, and “Recipient” where Spanish or French would otherwise require a gender inferred from a person.
12. The single root `404.html` remains English because the repository contains no server configuration capable of choosing an error document by locale.
13. Translation-provider selection and credentials belong only to the authoring command; no provider client, credential, or network call enters `website/build.py`.
14. The current uncommitted change that keeps the mobile navigation closed in `datasets/website/templates/base.html:29` is user work and MUST be preserved during implementation.

## Scope and estimated size

The implementation is expected to touch **39 source files**, approximately **+1,900 / -650 LOC**, plus generated catalogue content. Current line ranges identify the actual code to inspect and edit; new files have no current range.

| File and current range | Expected change |
|---|---|
| `datasets/website/build.py:38-3224` | language/catalogue model, localized planning, stable keys, metadata, generated artifacts, rendering, full and home-only build paths and CLI reporting |
| `datasets/website/i18n/en.toml` (new) | authoritative English segments, UI, terms, ranking copy, and plural forms |
| `datasets/website/i18n/es.toml` (new) | committed Spanish catalogue plus reviewed-key manifest |
| `datasets/website/i18n/fr.toml` (new) | committed French catalogue plus reviewed-key manifest |
| `datasets/website/i18n/labels.toml` (new) | committed institution labels keyed by QID and language |
| `datasets/scripts/fetch_wikidata_labels.py` (new) | explicit Wikidata label authoring command |
| `datasets/scripts/translate_catalogue.py` (new) | explicit machine-translation, merge, review-preservation, and validation command |
| `datasets/website/templates/base.html:1-71` | `lang`, translated chrome, alternates, switcher, localized metadata |
| `datasets/website/templates/index.html:1-120` | home copy, counts, labels, and terms |
| `datasets/website/templates/awards.html:1-9` | awards-index copy |
| `datasets/website/templates/_awards.html:1-21` | shared award-list labels |
| `datasets/website/templates/prize.html:1-48` | prize-page copy and translated terms |
| `datasets/website/templates/winners.html:1-30` | complete-winner-list copy and table headings |
| `datasets/website/templates/category.html:1-28` | category-page copy |
| `datasets/website/templates/year.html:1-31` | year-page headings and accessibility labels |
| `datasets/website/templates/winner.html:1-64` | recipient labels while preserving motivations |
| `datasets/website/templates/person.html:1-33` | person-page labels and translated linked terms |
| `datasets/website/templates/people.html:1-26` | people-index copy and pagination |
| `datasets/website/templates/_view_tabs.html:1-18` | translated subject and country tab labels |
| `datasets/website/templates/countries.html:1-20` | country-index copy and translated names |
| `datasets/website/templates/country.html:1-22` | country-detail copy and translated display name |
| `datasets/website/templates/affiliation_countries.html:1-22` | institution-country-index copy and translated countries |
| `datasets/website/templates/affiliation_country.html:1-29` | institution-country-detail copy and translated country |
| `datasets/website/templates/affiliations.html:1-44` | institution-index copy |
| `datasets/website/templates/affiliation.html:1-43` | institution-page UI; recorded description and proper name remain source text on fallback |
| `datasets/website/templates/universities.html:1-34` | university ranking copy |
| `datasets/website/templates/university_countries.html:1-34` | university country-view copy and translated countries |
| `datasets/website/templates/subjects.html:1-21` | subject-index copy and terms |
| `datasets/website/templates/subject.html:1-27` | subject people-view copy and terms |
| `datasets/website/templates/subject_affiliations.html:1-29` | subject institution-view copy and terms |
| `datasets/website/templates/subject_recent.html:1-34` | recent-subject copy and terms |
| `datasets/website/templates/explorer.html:1-658` | translated HTML, payload strings, locale-aware sorting/numbers, and JS accessibility text |
| `datasets/website/templates/nearby.html:1-148` | translated HTML and all browser-generated status/result/error text |
| `datasets/website/templates/map.html:1-477` | translated HTML, controls, popups, filters, totals, and JS accessibility text |
| `datasets/website/templates/about.html:1-170` | all editorial site copy |
| `datasets/website/templates/404.html:1-17` | catalogue lookups compatible with the English-only root error render |
| `datasets/website/static/style.css:57-91,852-910` | compact language-switcher styling integrated with current responsive navigation |
| `datasets/tests/test_build_website.py:135-2475` | catalogue, routing, parity, rendering, generated-output, and regression tests |
| `AGENTS.md:94-133` | multilingual build, routes, catalogue authoring, `llms.txt`, and offline guarantees |

`datasets/website/templates/country_views.html:1-14` is not in `TEMPLATES`, is not selected by any `PageJob`, and is excluded. The implementation MUST NOT delete or refactor it as part of this feature.

## Catalogue contract

Each locale file contains these closed sections:

| Section | Identity and coverage |
|---|---|
| top level | exact `code`, URL `prefix`, and a parseable `reviewed` list of fully qualified catalogue keys |
| `segments` | every semantic segment: awards, people, countries, awarded, died, affiliations, universities, subjects, explorer, nearby, map, about, winners, recent, and paginated-page |
| `ui` | template copy, generated titles/descriptions/breadcrumbs, fact labels, metadata/share-image text, `llms.txt` prose, JavaScript strings, accessibility labels, and plural forms |
| `terms.prize` | every `award_ranking.prize_name` and every live award prize name; currently 16 |
| `terms.category` | every distinct nonblank `awards.category`; currently 86 |
| `terms.country` | every country token rendered from award and affiliation data; currently 87 |
| `terms.subject` | the union of every nonblank `high_school_subject` and every configured `SUBJECTS` value; currently 10 because map routes exist for all 10 |
| `terms.laureate_type` | `Individual` and `Organization` |
| `ranking.<award_qid>` | localized rendered `blurb` for every ranking row; currently 16 |

All `ui` keys containing dots MUST be quoted so TOML parses them as flat keys. `Language.text()` and `Language.term()` MUST raise `BuildFailure` with the language and missing key. Formatting failures, extra arguments, and missing placeholders MUST also be mapped to a concise `BuildFailure` rather than escaping from a render worker.

Pluralized catalogue entries use `<key>.one` and `<key>.other`. Server code selects with the language rule; browser code uses `Intl.PluralRules(language.code)`. Generated HTML uses a pure deterministic `format_number(value, code)` helper and browser UI uses `Intl.NumberFormat(language.code)`. Implementation MUST NOT call process-global `locale.setlocale()`, which would race across the existing eight render workers.

Spanish and French `reviewed` lists are data, not comments. `translate_catalogue.py` reads an existing target catalogue, copies every reviewed value byte-for-byte, translates only unreviewed English values, and writes a complete replacement atomically after all validation succeeds. A comment marker is insufficient because `tomllib` discards comments.

## Language model and preflight

A small immutable `Language` value owns the locale code, prefix, semantic segments, UI strings, controlled terms, ranking copy, institution labels, plural selection, number formatting, and route construction. It is passed through planning and rendering; it is not mutable module state.

`load_languages()` MUST parse all four committed TOML inputs and validate them before any `PageJob`, staging directory, or output file is created. With the database already read once, preflight compares all closed vocabulary sections with the actual values that the planner can render. Unknown extra catalogue keys MAY remain for forward compatibility, but missing live values, duplicate codes/prefixes, empty or invalid segment slugs, invalid QIDs, mismatched placeholders, and absent ranking fields MUST fail with one concise language-and-key error.

English route-driving data is additionally pinned: prefix is empty; semantic segments equal the current English constants and nested components; and `slugify()` of every English category, country, and configured subject term equals `slugify()` of its source value. Any violation MUST fail preflight. English display-copy edits remain possible only where they do not move a public route.

Institution labels have a different contract. English always returns the recorded `affiliation_name`, preserving the English-Wikipedia-title rule in `AGENTS.md:24-29`. Spanish and French use `labels.toml` when the locale has a nonblank label for that exact QID and otherwise return the recorded institution name. `entity_label()` MUST NOT use name similarity, an English Wikidata label, or a label from another QID. Constituent units remain exactly as recorded.

The build MUST read `awards.sqlite3` only once and construct each locale from the same rankings, profiles, and award records. English, Spanish, and French must enter the same planner path. `build_home_page()` MUST load the same catalogues and render only the English home page into an existing build; it MUST NOT rewrite or invalidate Spanish or French pages.

## Routing, page identity, and parity

English routes remain byte-for-byte unchanged. Spanish and French prefix the path and localize every semantic fixed segment. Category, country, and subject slugs are derived by applying the current `slugify()` behavior to their translated catalogue term. Canonical prize slugs still come from `award_ranking.slug`; person slugs still derive from `full_name`; institution slugs still use `affiliation_slug()`; award years and record-name components remain unchanged.

The route builder MUST cover nested segments rather than concatenating English constants. This includes winner lists, country membership views, institution-by-country views, subject recent views, map subject views, and people pagination. Language-specific reserved country slugs are built from that language's nested country segments and checked before country pages are accepted.

Every `PageJob` gains a locale and one stable key from this complete family map:

| Page family | Language-independent key |
|---|---|
| Home, awards, people page N | `home`, `awards`, `people:<n>` |
| Prize, complete winners | `prize:<award_qid>`, `prize-winners:<award_qid>` |
| Category | `category:<award_qid>:<canonical-category-slug>` |
| Category year, all-category prize year | `category-year:<award_qid>:<canonical-category-slug>:<year>`, `prize-year:<award_qid>:<year>` |
| Award recipient | `winner:<award_record_id>` |
| Merged person | `person:<laureate_qid>` |
| Country indexes | `countries:<born|awarded|died>` |
| Country detail | `country:<born|awarded|died>:<canonical-country-slug>` |
| Institution country index/detail | `affiliation-countries`, `affiliation-country:<canonical-country-slug>` |
| Institution index/detail | `affiliations`, `affiliation:<canonical-affiliation-slug>` |
| Universities overall/by country | `universities`, `universities:countries` |
| Subjects index/people/institutions/recent | `subjects`, `subject:<canonical-subject-slug>:<people|affiliations|recent>` |
| Map overall/by subject | `map`, `map:<canonical-subject-slug>` |
| Explorer, nearby, about | `explorer`, `nearby`, `about` |

Keys MUST use database identity or canonical English source values, never localized display text. Person keys remain QID-only because `person_routes()` already omits unverified identities. Winner keys retain `award_record_id`, so unmerged recipients still have multilingual award pages.

Planner values that are grouped, joined, or tie-broken by name MUST retain an explicit canonical source name alongside a localized display label. Identity, membership, stable keys, ranking ties, and existing ordering use canonical values; templates, localized metadata, and localized slug derivation use display values only. Translated labels MUST never become dictionary keys or branch sentinels. Existing English control tokens such as country-view kind, fact-field identity, and `ShareCard.kind` remain stable internal identifiers with separate translated labels.

After all three plans are built, the builder groups jobs by key. Every key MUST have exactly one `en`, one `es`, and one `fr` job. Missing siblings, duplicate locale members, duplicate routes within a locale, cross-locale route collisions, and localized slug collisions MUST fail before rendering and name the key, locale, and route involved.

Route-prefix conditionals such as `share_image_target()` MUST classify a page from its stable key or template, not English path prefixes.

## Alternates, metadata, and navigation

Each rendered page receives the route map for its stable key. `base.html` MUST:

- set `<html lang>` to the locale code;
- emit absolute canonical URLs for the current locale route;
- emit reciprocal `en`, `es`, and `fr` `<link rel="alternate" hreflang>` elements plus `x-default` pointing to English;
- build its language switcher from that exact alternate map, keeping the reader on the equivalent page;
- localize document titles, descriptions, Open Graph text, navigation, breadcrumbs, footer copy, and accessibility labels;
- preserve the user's current closed mobile-navigation behavior.

JSON-LD continues to carry source identities and facts, but localized breadcrumb labels, item-list display terms, URLs, and page descriptions MUST match the current page. The implementation SHOULD add the page language where schema.org supports `inLanguage`; it MUST NOT translate personal names, dates, source citations, registry IDs, or institution fallback names.

Sitemap generation receives all 22,035 current page routes and remains one sitemap while within both current limits. Sitemap entries do not replace HTML `hreflang` links. `robots.txt` and the root `awards.csv` remain shared language-neutral artifacts.

## Templates and browser-side UI

All user-visible English in the 29 loaded templates moves to catalogue lookups, including metadata-adjacent labels, table headings, link text, form controls, empty/error states, privacy notes, `aria-label` text, and inline JavaScript output. Brand names, official organization names, registry names, code tokens, and source data are not catalogue UI.

The Explorer, map, and nearby payloads gain only the localized values needed by their current JavaScript. Browser-generated sentences MUST read string templates supplied from the catalogue rather than embedding translated branches in JavaScript. Raw keys used for filtering and joining remain canonical; separate display labels carry translated countries and subjects. This prevents translated labels from breaking payload indexes, map filters, geo-IP country matching, or existing rank calculations.

Browser strings are emitted once as JSON in a non-executable `<script type="application/json">` payload using the existing `<`-escaping JSON contract or Jinja's `tojson`; they are parsed as data and MUST NOT be interpolated directly into JavaScript source. They use the same `{field}` placeholder syntax as server strings, with an allowed field set declared per key and checked by catalogue/translation validation. Runtime code substitutes fields into DOM text nodes or attributes. Catalogue strings MUST NOT enter `innerHTML`, `eval`, `Function`, or executable markup; UI that mixes text and links is assembled from DOM nodes.

JavaScript sorting uses the page language where it sorts translated display labels. Server-established rankings and person ordering remain unchanged per Assumption 8. Runtime numbers use `Intl.NumberFormat`, and plurals use `Intl.PluralRules` with catalogue one/other templates. The optional Explorer request to `api.country.is`, browser geolocation, and OpenStreetMap tile requests retain their current behavior; only their surrounding UI is localized.

Motivation text in `category.html`, `year.html`, and `winner.html` MUST be byte-identical across locale siblings and introduced, where a label exists, by translated UI copy. Institution profile descriptions and other excluded source prose remain unchanged.

## Generated machine-reader and social assets

`write_llms_txt()` currently emits English prose and English route constants from `datasets/website/build.py:2775-2875`. It MUST generate one guide per locale plan: root `llms.txt`, `/es/llms.txt`, and `/fr/llms.txt`. Each guide uses localized prose, terms, semantic URL patterns, winner-list routes, subject routes, and embedded-JSON page routes, while reporting the same source counts. These files remain outside the sitemap.

Social descriptions and share-card text MUST be localized. English keeps the current generated asset paths for compatibility; Spanish and French assets use locale-specific paths under `static/share/es/` and `static/share/fr/` so one locale cannot overwrite another. Prize and generic cards use the localized page URL, labels, prize/subject display terms, and number formatting. The underlying source identity and ranking values remain unchanged.

The single root 404 render receives the English language catalogue, empty alternates, and the current deployment-root link behavior. Locale-specific server error routing is out of scope.

## Authoring commands

`datasets/scripts/fetch_wikidata_labels.py` reads the exact distinct nonblank affiliation QIDs referenced by both primary and extra affiliation records, requests `es` and `fr` labels from the Wikidata API in bounded batches with timeouts, and atomically writes deterministic `labels.toml`. It reports only QIDs and aggregate `resolved`/`missing` counts; it MUST NOT log response bodies or unrelated data. A failed or malformed response leaves the existing file unchanged.

`datasets/scripts/translate_catalogue.py` reads `en.toml` and the existing target locale, invokes the configured authoring-time machine-translation provider for unreviewed strings, preserves reviewed keys, and atomically replaces the target only after completeness and placeholder validation. Provider credentials come from the environment and MUST NOT be printed or written to catalogues. Provider-specific setup is documented by the script's CLI help, not imported by the website builder.

For every formatted string, the translator compares the multiset of Python format fields before and after translation. Renamed, added, removed, malformed, or duplicated fields fail with locale and catalogue key; reordering is allowed. A glossary pins recurring site terms. Completion reports `translated=N preserved=M failed=K` without logging the source or translated prose.

Both authoring commands run manually and their outputs are reviewed and committed. Neither command is called by `website/build.py`, tests that build the site, or the home-only path.

## Failure, compatibility, and rollout

Catalogue and parity failures occur before staging creation. Worker, social-image, sitemap, CSV, `llms.txt`, 404, and pre-promotion permission failures retain the current staging cleanup and leave the existing `website/dist/` in place. `_promote()` currently deletes `dist/` before renaming staging (`datasets/website/build.py:3144-3147`); making that final replacement rollback-safe is a separate deployment change and is not claimed by this specification.

No database table, column, or value changes. No redirect is introduced. Every English canonical URL, CSV location, prize slug, person slug, institution slug, and public English share-image path remains valid. New localized routes and assets are additive.

The implementation uses the repository's current no-branch workflow from `AGENTS.md:4`, preserves unrelated work, uses conventional commits when committing, and adds unit tests with implementation. No merge or squash workflow is introduced.

## Behavioral acceptance

### Requirement: English public contracts MUST remain stable

#### Scenario: root-language build
- WHEN the multilingual build completes against the current database
- THEN every pre-change English page route exists at the identical path
- AND English canonical URLs, prize/person/institution slugs, `awards.csv`, `robots.txt`, and current English share-image paths are unchanged
- AND no English route starts with `/en/`

### Requirement: Every generated page MUST have complete locale parity

#### Scenario: three siblings per stable key
- WHEN all locale plans are joined
- THEN every stable key has exactly one English, Spanish, and French page
- AND the current 7,345-page source plan produces 22,035 page jobs
- AND missing or duplicate siblings fail before rendering with key and locale details

#### Scenario: localized collision
- WHEN two translated categories, countries, subjects, or reserved segments produce the same route in one locale
- THEN preflight fails naming the locale, route, and both owners
- AND the existing `dist/` remains untouched

### Requirement: Alternates and switching MUST be reciprocal

#### Scenario: switch a person page
- WHEN a reader opens the Spanish sibling of an English person page
- THEN canonical metadata names the Spanish URL
- AND `hreflang` names the English, Spanish, French, and English `x-default` URLs
- AND the French switcher link reaches the French sibling rather than the French home page
- AND every sibling publishes the reciprocal links

### Requirement: Catalogues MUST be complete and safe

#### Scenario: closed-vocabulary miss
- WHEN any configured locale lacks a live segment, UI key, ranking field, prize, category, country, subject, or laureate-type term
- THEN `load_languages()` raises `BuildFailure` naming the locale and key before staging exists

#### Scenario: institution-label miss
- WHEN an affiliation has no QID or its exact QID has no target-language label
- THEN the page renders the recorded institution name and the build succeeds

#### Scenario: format field corruption
- WHEN machine translation renames, adds, drops, duplicates, or malforms a format field
- THEN the authoring command fails naming the locale and key
- AND it does not replace the target catalogue

#### Scenario: reviewed translation
- WHEN a reviewed target key exists and translation is rerun
- THEN its value remains byte-identical
- AND the completion counts it as preserved

### Requirement: Source prose MUST retain provenance

#### Scenario: localized award recipient
- WHEN the same award-recipient page renders in all three languages
- THEN its motivation is byte-identical in every page
- AND only the surrounding label, title, metadata, navigation, and controlled terms are localized

#### Scenario: excluded profile prose
- WHEN an institution page contains a stored profile description
- THEN that description and any constituent-unit name remain unchanged across locales

### Requirement: Browser UI MUST use the page locale

#### Scenario: Explorer, map, and nearby interactions
- WHEN JavaScript creates a tooltip, popup, result row, status, error, count, or accessibility label
- THEN it uses catalogue strings and the page language's number and plural rules
- AND canonical filter/join keys still select the same records as English
- AND no visible English fallback is silently inserted for a missing required string

### Requirement: Full and partial builds MUST share one language contract

#### Scenario: offline full build
- WHEN `uv run website/build.py --base-url https://example.org/awards/` runs with valid committed catalogues
- THEN it makes no translation or Wikidata-label request
- AND it generates all locale pages, localized `llms.txt` files, localized share assets, one sitemap, shared CSV/robots files, and the English root 404 before the existing final promotion step

#### Scenario: home-only refresh
- WHEN `--home-only` runs against an existing multilingual `dist/`
- THEN it refreshes only the English root homepage using the English catalogue
- AND Spanish, French, sitemap, CSV, social assets, and other pages remain byte-identical

## Verification

Implementation verification MUST include:

1. `uv run python -m unittest tests/test_build_website.py`
2. `uv run ruff check website/build.py scripts/fetch_wikidata_labels.py scripts/translate_catalogue.py tests/test_build_website.py`
3. `uv run website/build.py --base-url https://example.org/awards/`
4. A pre/post manifest comparison proving every existing English route remains present.
5. HTML checks for reciprocal canonical/`hreflang`/switcher URLs on at least one page in every page family.
6. JSON parsing for Explorer, map, nearby, and JSON-LD payloads plus JavaScript syntax checks for the three browser-heavy templates.
7. Assertions that current page parity is 7,345 × 3, the sitemap contains all 22,035 page routes, and it remains a single sitemap at the current snapshot.
8. Byte comparisons for motivations, excluded profile prose, reviewed translation values, and unaffected files after `--home-only`.
9. A network-call guard proving the full and home-only website build paths never invoke either authoring command or an HTTP client.
10. Mocked authoring-command tests covering exact primary-plus-extra QID selection, batching, deterministic output, safe aggregate logging, provider/API failure, malformed data, reviewed-key preservation, placeholder failures, and byte-identical destination files after every failed run.

## Out of scope

- Translating award motivations, biographical notes, institution profile descriptions, personal names, constituent units, city names, dates, identifiers, or source URLs.
- Modifying `awards.sqlite3`, `award_ranking.toml`, `population.json`, affiliation identity, ranking/scoring behavior, or any generated dataset value.
- Translating the unused `award_ranking.reasoning` field until a page or generated public artifact renders it.
- Language auto-detection, redirects, cookies, locale preferences, or locale-specific server configuration.
- A localized root/server-selected 404 response.
- Professional human translation of every string; durable review markers support incremental corrections.
- German, CJK, right-to-left layout, locale-specific search stemming, or additional plural categories beyond those needed by English, Spanish, and French.
- Refactoring or deleting the unused `country_views.html` template.
- Changing the current destructive final promotion algorithm; this translation feature retains its existing tested semantics without claiming rollback safety.
