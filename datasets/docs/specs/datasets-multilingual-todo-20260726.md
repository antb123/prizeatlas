# TODO — Multilingual PrizeAtlas (English, Spanish, French)

Implementation plan for `datasets/docs/specs/datasets-multilingual-20260726.md`. Run commands from `datasets/`. The current baseline is 51 passing website tests and a 7,696-page plan measured on 2026-08-02. The repository uses its current no-branch workflow; preserve unrelated changes, especially the collapsed mobile navigation in `website/templates/base.html:29`.

**Verification is local to each task.** Every task below owns the tests that prove it and adds them to `tests/test_build_website.py` in the same change. T10 holds only the cross-cutting checks that genuinely require the whole feature to exist. An earlier draft of this plan deferred all verification to T10 while T10 depended on T1-T9, which left nine tasks with no gate of their own; that is fixed here.

Numbers quoted below (7,696 pages, 349 cities, 87 countries, 574 QIDs) are a 2026-08-02 snapshot. Tests MUST derive expected totals from a pre-change plan of the same database rather than hard-coding them.

## T1 — Author the complete English catalogue

**ID:** T1 — Create the route and copy source of truth.

**Depends-on:** none.

**Files:** `website/i18n/en.toml` (new); `tests/test_build_website.py`.

**Assumptions:**

1. English remains at the root with no `/en/` routes or redirects.
2. Semantic segments and category/country/subject slugs are localized; prize, person, institution, city, year, and recipient components remain canonical.
3. Motivations, biographical notes, institution descriptions, personal names, constituent units, and city names remain source text.
5. `website/i18n/en.toml` is the hand-authored catalogue source.
6. Missing closed-vocabulary entries fail preflight.
10. Number separators are pinned per locale, not inherited.
12. English person-facing copy uses neutral nouns such as "Birth", "Death", and "Recipient".

**Steps → verify:**

1. Create the top-level `code`, `prefix`, pinned `group`/`decimal` separators, and parseable `reviewed` fields plus `segments`, flat quoted `ui`, `terms.prize`, `terms.category`, `terms.country`, `terms.subject`, `terms.laureate_type`, and `ranking.<qid>.blurb` sections.
2. Pin every English semantic segment to the current route constants and nested components in `website/build.py:80-115,127,2357,2404`, including `cities`, `cities-per-capita`, and both distinct affiliation segments (`country_affiliations` from line 91 and `affiliations` from line 98).
3. Extract all generated and template UI, metadata, accessibility, browser, share-image, and `llms.txt` copy from `website/build.py:1015-3294` and the 30 loaded templates.
4. Include all 16 prizes, 86 nonblank categories, 87 rendered country tokens, both laureate types, all live subjects, and all 10 configured `SUBJECTS` values used by map routes.
5. Add the composite city-label copy that joins a frozen city name to a `terms.country` value, as one formatted string with declared fields — never a runtime string replacement inside a joined name.
6. Copy the 16 rendered English ranking blurbs; do not copy unused ranking reasoning or excluded source prose.
7. Define one/other plural pairs and explicit `{field}` placeholders with an allowed field set per browser string.
8. **Own tests:** TOML parses; every required key exists; the segment list is complete against the route constants; English prefix is empty; English route-driving term slugs equal source slugs; the two affiliation segments are distinct keys; no excluded source prose appears; English separators are `,`/`.`.

## T2 — Fetch committed Wikidata institution labels

**ID:** T2 — Build the explicit label-authoring command and label snapshot.

**Depends-on:** none.

**Files:** `scripts/fetch_wikidata_labels.py` (new); `website/i18n/labels.toml` (new, generated); `tests/test_build_website.py`.

**Assumptions:**

3. Institution fallback names and constituent units remain recorded source text.
4. Label fetching is an explicit authoring command; the website build stays offline.
6. Missing Spanish/French institution labels fall back instead of failing.
14. Authoring credentials and network clients never enter `website/build.py`.

**Steps → verify:**

1. Read distinct nonblank affiliation QIDs from both primary award affiliations and `award_extra_affiliations` using a read-only SQLite connection; the union is currently 574.
2. Request only Spanish and French Wikidata labels in bounded batches with a timeout; validate exact QIDs and string values.
3. Write deterministic TOML through a temporary file and replace `labels.toml` only after the complete response validates.
4. Log only QIDs needed to diagnose a miss and aggregate `resolved=N missing=M`; never log response bodies or labels.
5. Run the command once to create the committed snapshot.
6. **Own tests (mocked, no network):** exact primary-plus-extra QID union; batching; stable ordering; malformed and failing responses leave the destination byte-identical; logs carry no label text.
7. `uv run ruff check scripts/fetch_wikidata_labels.py`.

## T3 — Implement catalogue translation and validation

**ID:** T3 — Translate unreviewed catalogue values without losing corrections.

**Depends-on:** T1.

**Files:** `scripts/translate_catalogue.py` (new); `tests/test_build_website.py`.

**Assumptions:**

3. Excluded source prose never enters the translation catalogue.
4. Machine translation runs only as an authoring command.
5. Spanish/French are committed machine-translated drafts with durable reviewed-key manifests.
6. Missing closed vocabulary fails; no incomplete target is written.
14. Provider selection and credentials are isolated to this command.

**Steps → verify:**

1. Read `en.toml` and an existing target catalogue; accept only `es` or `fr` targets.
2. Preserve every target value named by its parseable `reviewed` list byte-for-byte; fail if a reviewed key is absent.
3. Translate only unreviewed values through the configured authoring provider and glossary.
4. Compare the multiset of `{field}` placeholders for every source/target value, including browser strings; allow reordering but reject renamed, added, removed, malformed, or duplicated fields.
5. Never translate the pinned separator fields; carry them from the target's own declaration.
6. Validate complete structural/key parity before atomically replacing the destination. On any provider, parse, placeholder, or validation error, leave it byte-identical.
7. Print `translated=N preserved=M failed=K` without source/target prose or credentials.
8. **Own tests (mocked provider):** placeholder reordering accepted; renamed/added/dropped/duplicated fields rejected; reviewed values preserved byte-for-byte; complete rollback on every failure class; glossary applied; logs carry no prose or credentials.
9. `uv run ruff check scripts/translate_catalogue.py`.

## T4 — Generate Spanish and French catalogues

**ID:** T4 — Commit complete target-language catalogues.

**Depends-on:** T1, T3.

**Files:** `website/i18n/es.toml` (new); `website/i18n/fr.toml` (new); `tests/test_build_website.py`.

**Assumptions:**

1. Prefixes are `/es/` and `/fr/`.
2. Every semantic segment and category/country/subject slug is localized.
5. Generated catalogues are committed and reviewed keys survive regeneration.
6. Closed-vocabulary misses fail the build.
10. Dates remain ISO; numeric values do not change; separators are pinned.
11. Browser/server plural selection uses each language code.

**Steps → verify:**

1. Run T3 for Spanish and French and set every semantic segment, including winners, country views, cities, cities-per-capita, recent, map, about, and pagination.
2. Set the pinned separators: Spanish `.`/`,`, French U+202F and `,`.
3. Review and mark navigation, accessibility/error text, 16 prize names, 87 country names, 10 subjects, 86 categories, the city composite label, and high-visibility headings.
4. Confirm every English key and placeholder multiset exists in both targets and every route-driving term produces a nonblank ASCII-folded slug.
5. **Own tests:** structural parity with `en.toml`; no missing key; every localized category/country/subject slug is nonblank and unique within its locale; no localized country slug equals that locale's `cities`, `cities-per-capita`, `awarded`, `died`, or `country_affiliations` segment; French one/other selection for 0, 1, and 2 and Spanish/English selection for the same values; declared separators match `Intl.NumberFormat` output for that locale.

## T5 — Localize planning, routing, generated outputs, and render control

**ID:** T5 — Make `Language` an explicit value through the one website build path.

**Depends-on:** T1, T2, T4.

**Files:** `website/build.py:38-3426`; `tests/test_build_website.py`.

**Assumptions:**

1. English URLs remain rooted and unchanged.
2. Semantic/category/country/subject paths localize; canonical entity components do not.
3. Source prose remains unchanged.
4. The website build performs no translation/label network work.
6. Closed lookups fail; institution labels fall back.
7. Stable page keys join locale siblings.
8. City labels are half frozen and half controlled; city slugs stay canonical.
9. Identity, rank, membership, and ordering remain canonical.
10. Server number formatting reads pinned separators and changes presentation only.
11. Plurals use the locale code.
13. The root 404 remains English.
14. Provider code stays outside the builder.

**Steps → verify:**

1. Add the immutable language/catalogue value and load/validate all committed TOML after the single database read but before planning or staging. Failure messages name locale, section, and exact missing value.
2. Enforce exact English prefix/segments and source-equivalent English category/country/configured-subject slugs.
3. Keep canonical source names/control tokens separate from localized display labels throughout country, city, affiliation, subject, Explorer, map, facts, and share-card logic; never group, join, rank, or branch on translated text.
4. Route every current page family through language-owned segments, including nested country views, the cities index, all 349 city detail pages, the cities-per-capita page, winner lists, people pagination, subject recent pages, institution-country pages, and all 10 map subject pages.
5. Rebuild `RESERVED_COUNTRY_SEGMENTS` per language from that language's own segment values so a translated country cannot shadow `cities` or `cities-per-capita`.
6. Implement the city label split from the spec: localized composite for display; canonical `members_by_place` keys, sort order, slug, and duplicate-slug guard at `website/build.py:1302-1345`.
7. Add the complete stable key map from the spec — including `cities`, `city:<canonical-city-slug>`, and `cities-per-capita` — to `PageJob`; require exactly one en/es/fr member per key and reject per-locale/cross-locale route or slug collisions before staging.
8. Build reciprocal alternate maps and classify share images from keys/templates rather than English route prefixes (`share_image_target()` at `website/build.py:1026`).
9. Add the pure `format_number(value, code)` helper reading pinned separators; no `locale.setlocale()`.
10. Localize titles, descriptions, breadcrumbs, facts, terms, ranking blurbs, JSON-LD display values, and social descriptions/cards; English institution display always uses the recorded name.
11. Preserve raw canonical keys beside localized labels in Explorer/map/nearby payloads so filters, geo-IP matching, the city per-capita view, membership, and ranks do not change.
12. Generate root, Spanish, and French `llms.txt`; retain one root CSV/robots/sitemap; preserve current English share paths and write target-locale shares under locale directories.
13. Keep `render_error_page()` English with empty alternates. Make `build_home_page()` validate the same catalogues but rewrite only the English root homepage. Keep CLI completion counts truthful for the combined plan.
14. Retain current pre-promotion cleanup and existing `_promote()` semantics at `website/build.py:3342-3345`; do not claim or implement rollback-safe promotion in this feature.
15. **Own tests:** catalogue load failure naming locale/section/value; English route pinning; stable-key completeness across all families including cities; exactly three members per key; per-locale and cross-locale collision rejection; reserved-segment collision rejection; canonical membership/ordering unchanged versus a pre-change plan; `format_number` equals `Intl.NumberFormat` output per locale; institution fallback returns the recorded name; city slug identical across locales.
16. `uv run ruff check website/build.py`. The whole-build gate is T12.

## T6 — Localize site chrome and style the switcher

**ID:** T6 — Render language metadata/navigation consistently at every depth.

**Depends-on:** T5.

**Files:** `website/templates/base.html:1-70`; `website/static/style.css:57-94,876-920,960-964`; `tests/test_build_website.py`.

**Assumptions:**

1. English root and `/es/`/`/fr/` prefixes are fixed.
7. The stable-key alternate map drives both `hreflang` and switching.
13. Root 404 is English.
15. The collapsed mobile navigation at `base.html:29` must survive.

**Steps → verify:**

1. Set the HTML language, localize chrome/metadata/accessibility/footer copy, and emit canonical plus reciprocal en/es/fr and English `x-default` alternates.
2. Build the switcher from the exact alternate map so it keeps the current stable page identity.
3. Handle empty alternates for root 404 without `StrictUndefined` failures.
4. Add compact switcher styles using current variables and the existing responsive navigation blocks; do not add `open` to the mobile details element.
5. **Own tests:** rendered `<html lang>`, canonical, four alternate links, and switcher targets at the root and at a deep route in each locale; 404 renders with empty alternates; `base.html:29` still has no `open` attribute.

## T7 — Localize server-rendered page templates

**ID:** T7 — Move non-browser page UI to catalogue lookups.

**Depends-on:** T5.

**Files:** `website/templates/index.html:1-120`; `awards.html:1-9`; `_awards.html:1-21`; `prize.html:1-47`; `winners.html:1-30`; `category.html:1-28`; `year.html:1-31`; `winner.html:1-63`; `person.html:1-33`; `people.html:1-26`; `_view_tabs.html:1-20`; `countries.html:1-20`; `country.html:1-22`; `city_per_capita.html:1-19`; `affiliation_countries.html:1-22`; `affiliation_country.html:1-29`; `affiliations.html:1-44`; `affiliation.html:1-43`; `universities.html:1-34`; `university_countries.html:1-34`; `subjects.html:1-21`; `subject.html:1-27`; `subject_affiliations.html:1-29`; `subject_recent.html:1-34` (all under `website/templates/`); `tests/test_build_website.py`.

**Assumptions:**

2. Display terms and relevant slugs localize; proper-name slugs do not.
3. Motivations, notes, institution descriptions, people, units, and cities remain source text.
6. Required UI/terms never silently fall back.
8. City headings render the localized composite.
9. Membership and ordering remain canonical.
10. Dates remain ISO; numbers use the pinned separators.
12. Person-facing copy is gender-neutral.

**Steps → verify:**

1. Replace every visible English UI literal, plural branch, table/control/accessibility label, and generated link phrase with catalogue output from T5.
2. Render translated prize/category/country/subject/laureate-type terms and exact-QID institution labels without using display strings for conditions such as the birth-country fact class.
3. `country.html` and `countries.html` serve both country and city pages — render the localized city composite on the city path and the plain translated country name on the country path, driven by the page's stable key rather than by inspecting the label text.
4. `city_per_capita.html` headings, column labels, and rates use catalogue copy and `format_number`; the underlying rates and ordering are unchanged.
5. Keep motivations, biographical notes, institution descriptions, names, units, cities, identifiers, brands, official URLs, and registry names unchanged.
6. Localize the wrapper of the Ask-AI query while retaining cited source text; keep all query construction escaped.
7. **Own tests:** a rendered assertion per template family in all three locales; byte-equal excluded prose across siblings; no required bare English UI string in Spanish/French output; city heading halves behave per the spec scenario; per-capita rates byte-equal to English apart from separators.

## T8 — Localize Explorer, map, and nearby browser UI safely

**ID:** T8 — Translate runtime interactions without changing their data joins.

**Depends-on:** T5.

**Files:** `website/templates/explorer.html:1-648`; `website/templates/map.html:1-522`; `website/templates/nearby.html:1-148`; `tests/test_build_website.py`.

**Assumptions:**

3. Names, cities, motivations, and other excluded source data remain unchanged.
6. Missing browser UI strings fail preflight.
9. Rankings, membership, and ordering remain canonical.
10. Runtime numbers use the page locale without changing values.
11. Runtime plurals use `Intl.PluralRules`.

**Steps → verify:**

1. Replace HTML copy, controls, help/error/privacy text, chart labels, popups, tooltips, result rows, and all accessibility text with catalogue strings.
2. Emit browser strings once as `<script type="application/json">` using `<`-safe JSON; parse them as data and interpolate only validated `{field}` placeholders.
3. Insert catalogue output through DOM text/attribute APIs; remove any path that places catalogue strings in `innerHTML`, executable source, `eval`, or `Function`.
4. Keep canonical country/subject/city/record keys and localized display labels separately; preserve Explorer geo-IP alias matching, the city awards-per-capita view, map filters, payload indexes, nearby routes, and server rank order.
5. Use `Intl.NumberFormat(language.code)` and `Intl.PluralRules(language.code)` for runtime output and locale-aware sorting only for translated display labels.
6. **Own tests:** each JSON payload parses; built scripts syntax-check; representative success and error states exercised; catalogue text containing `<script>` is rendered inert; English versus localized record selection, city per-capita ordering, and ranks compared for equality.

## T9 — Localize editorial About copy and keep root 404 compatible

**ID:** T9 — Translate long-form site copy and the English error document.

**Depends-on:** T5.

**Files:** `website/templates/about.html:1-176`; `website/templates/404.html:1-17`; `tests/test_build_website.py`.

**Assumptions:**

3. Source dataset prose is excluded, but authored website editorial copy is translated.
6. Required UI copy fails on a miss.
13. The one root 404 remains English, and its links lead to English pages.

**Steps → verify:**

1. Replace all About editorial copy, headings, totals, link phrases, and accessibility text with catalogue values while preserving brand/license/official-link identities.
2. Replace 404 literals with catalogue lookups that render from the English language object and empty alternates.
3. **Own tests:** About renders in all three plans with no bare English in the localized output; 404 renders exactly once at root; no locale-specific error route is introduced.

## T10 — Cross-cutting integration tests

**ID:** T10 — Prove the contracts that only hold once every part exists.

**Depends-on:** T1-T9.

**Files:** `tests/test_build_website.py`.

**Assumptions:** all 15 assumptions from the specification.

This task adds only what cannot be proven inside a single earlier task. Per-task tests belong to their tasks.

**Steps → verify:**

1. Full three-locale parity over a complete plan: every stable key has exactly one en/es/fr member, and the total equals a pre-change plan of the same database × 3.
2. English route manifest: build a pre-change plan and a post-change plan from the same database and assert every English route, prize/person/city/institution slug, and English share path is present and unchanged, and that no route starts with `/en/`.
3. Localized `llms.txt` at root, `/es/`, and `/fr/`; one shared sitemap containing every page route; shared CSV and robots; locale share assets under `static/share/es/` and `static/share/fr/`.
4. Home-only refresh against a completed multilingual build leaves every file except `dist/index.html` byte-identical.
5. Build-time network prohibition: neither the full path nor the home-only path invokes an authoring command or an HTTP client.
6. Server/browser number-formatting equivalence across all three locales on shared fixtures.
7. `uv run python -m unittest tests/test_build_website.py` passes and `uv run ruff check tests/test_build_website.py` is clean.

## T11 — Update repository guidance

**ID:** T11 — Document the implemented authoring and build contract.

**Depends-on:** T5.

**Files:** `AGENTS.md:94-133` (repository root).

**Assumptions:**

1. English root and Spanish/French prefixes are fixed.
3. Source prose exclusions are permanent product rules.
4. Website builds are offline; authoring commands are explicit.
5. English is the catalogue source and target catalogues are committed.
6. Closed-vocabulary misses fail both the full build and `--home-only`.
13. Root 404 is English.

**Steps → verify:**

1. Document locale prefixes, localized semantic/category/country/subject routes, canonical proper-name and city routes, and `hreflang`/switcher behavior.
2. Document catalogue locations, reviewed-key regeneration, label and translation commands, source-prose exclusions, and the no-network builder guarantee.
3. State the enrichment consequence explicitly: adding an award row with a new country, category, or prize name fails the build and `--home-only` until `translate_catalogue.py` is rerun for both targets and the result committed.
4. Update `llms.txt`, share-image, sitemap/page-count, home-only, and 404 descriptions to match implementation.
5. Verify every named file/command exists and guidance does not claim rollback-safe promotion or branch use.

## T12 — Full regression and public-contract gate

**ID:** T12 — Verify the complete implementation without modifying source files.

**Depends-on:** T1-T11.

**Files:** none.

**Assumptions:** all 15 specification assumptions.

**Steps → verify:**

1. Capture the current English route/share-asset manifest, then run `uv run website/build.py --base-url https://example.org/awards/`.
2. Verify the build reports 16 prizes, the pre-change plan size per locale (currently 7,696), three times that in sitemap page URLs (currently 23,088), exactly three siblings per stable key, and one sitemap at the current snapshot.
3. Compare manifests: every prior English page and public English share path remains; no `/en/` route exists; CSV/robots paths remain shared.
4. Check reciprocal canonical/`hreflang`/switcher links, localized semantic routes, a city detail page in each locale, root/Spanish/French `llms.txt`, locale share assets, and the English root 404.
5. Prove motivations and excluded profile/unit/name/city/date content are byte-identical across siblings and ranks/membership match English.
6. Run `uv run python -m unittest tests/test_build_website.py` and confirm all tests pass.
7. Run `uv run ruff check website/build.py scripts/fetch_wikidata_labels.py scripts/translate_catalogue.py tests/test_build_website.py` and confirm it is clean.
8. Run the home-only path against the completed build and verify only `website/dist/index.html` changes.
9. Confirm the full and home-only build made no label-fetch or translation-provider request and `git status --short` contains no generated `website/dist/` state.

## Prerequisite — unreadable build input

`website/city_populations.csv` is mode `0600` owned by `antb3`. Any other account, including `antb2`, gets `PermissionError` from `load_city_populations()` at `website/build.py:517` and cannot run a full build or the T12 gate. Fix the mode before starting T5. This is a pre-existing repository condition, not something this feature introduces.
