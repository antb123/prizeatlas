# TODO — Multilingual PrizeAtlas (English, Spanish, French)

Implementation plan for `datasets/docs/specs/datasets-multilingual-20260726.md`. Run commands from `datasets/`. The current baseline is 48 passing website tests and a 7,345-page build. The repository uses its current no-branch workflow; preserve unrelated changes, especially the closed mobile navigation in `website/templates/base.html:29`.

## T1 — Author the complete English catalogue

**ID:** T1 — Create the route and copy source of truth.

**Depends-on:** none.

**Files:** `website/i18n/en.toml` (new).

**Assumptions:**

1. English remains at the root with no `/en/` routes or redirects.
2. Semantic segments and category/country/subject slugs are localized; prize, person, institution, year, and recipient components remain canonical.
3. Motivations, biographical notes, institution descriptions, personal names, constituent units, and city names remain source text.
5. `website/i18n/en.toml` is the hand-authored catalogue source.
6. Missing closed-vocabulary entries fail preflight.
11. English person-facing copy uses neutral nouns such as “Birth”, “Death”, and “Recipient”.

**Steps → verify:**

1. Create the top-level `code`, `prefix`, and parseable `reviewed` fields plus `segments`, flat quoted `ui`, `terms.prize`, `terms.category`, `terms.country`, `terms.subject`, `terms.laureate_type`, and `ranking.<qid>.blurb` sections.
2. Pin every English semantic segment to the current route constants/nested components in `website/build.py:79-108,122,2500`.
3. Extract all generated and template UI, metadata, accessibility, browser, share-image, and `llms.txt` copy from `website/build.py:954-3136` and the 29 loaded templates.
4. Include all 16 prizes, 86 nonblank categories, 87 rendered country tokens, both laureate types, all live subjects, and all 10 configured `SUBJECTS` values used by map routes.
5. Copy the 16 rendered English ranking blurbs; do not copy unused ranking reasoning or excluded source prose.
6. Define one/other plural pairs and explicit `{field}` placeholders with an allowed field set per browser string.
7. Verify with the catalogue tests added in T10: TOML parses, every required key exists, English prefix/segments are pinned, English route-driving term slugs equal source slugs, and no excluded source prose appears.

## T2 — Fetch committed Wikidata institution labels

**ID:** T2 — Build the explicit label-authoring command and label snapshot.

**Depends-on:** none.

**Files:** `scripts/fetch_wikidata_labels.py` (new); `website/i18n/labels.toml` (new, generated).

**Assumptions:**

3. Institution fallback names and constituent units remain recorded source text.
4. Label fetching is an explicit authoring command; the website build stays offline.
6. Missing Spanish/French institution labels fall back instead of failing.
13. Authoring credentials and network clients never enter `website/build.py`.

**Steps → verify:**

1. Read distinct nonblank affiliation QIDs from both primary award affiliations and `award_extra_affiliations` using a read-only SQLite connection.
2. Request only Spanish and French Wikidata labels in bounded batches with a timeout; validate exact QIDs and string values.
3. Write deterministic TOML through a temporary file and replace `labels.toml` only after the complete response validates.
4. Log only QIDs needed to diagnose a miss and aggregate `resolved=N missing=M`; never log response bodies or labels.
5. Run the command once to create the committed snapshot.
6. Verify with T10 mocked tests: exact QID union, batching, stable ordering, malformed/failing response rollback with byte-identical destination, and safe logs; run `uv run ruff check scripts/fetch_wikidata_labels.py`.

## T3 — Implement catalogue translation and validation

**ID:** T3 — Translate unreviewed catalogue values without losing corrections.

**Depends-on:** T1.

**Files:** `scripts/translate_catalogue.py` (new).

**Assumptions:**

3. Excluded source prose never enters the translation catalogue.
4. Machine translation runs only as an authoring command.
5. Spanish/French are committed machine-translated drafts with durable reviewed-key manifests.
6. Missing closed vocabulary fails; no incomplete target is written.
13. Provider selection and credentials are isolated to this command.

**Steps → verify:**

1. Read `en.toml` and an existing target catalogue; accept only `es` or `fr` targets.
2. Preserve every target value named by its parseable `reviewed` list byte-for-byte; fail if a reviewed key is absent.
3. Translate only unreviewed values through the configured authoring provider and glossary.
4. Compare the multiset of `{field}` placeholders for every source/target value, including browser strings; allow reordering but reject renamed, added, removed, malformed, or duplicated fields.
5. Validate complete structural/key parity before atomically replacing the destination. On any provider, parse, placeholder, or validation error, leave it byte-identical.
6. Print `translated=N preserved=M failed=K` without source/target prose or credentials.
7. Verify with T10 mocked tests for placeholder reordering/failures, reviewed preservation, complete rollback, glossary application, safe logging, and provider failure; run `uv run ruff check scripts/translate_catalogue.py`.

## T4 — Generate Spanish and French catalogues

**ID:** T4 — Commit complete target-language catalogues.

**Depends-on:** T1, T3.

**Files:** `website/i18n/es.toml` (new); `website/i18n/fr.toml` (new).

**Assumptions:**

1. Prefixes are `/es/` and `/fr/`.
2. Every semantic segment and category/country/subject slug is localized.
5. Generated catalogues are committed and reviewed keys survive regeneration.
6. Closed-vocabulary misses fail the build.
9. Dates remain ISO; numeric values do not change.
10. Browser/server plural selection uses each language code.

**Steps → verify:**

1. Run T3 for Spanish and French and set every semantic segment, including winners, country views, recent, map, about, and pagination.
2. Review and mark navigation, accessibility/error text, 16 prize names, 87 country names, 10 subjects, 86 categories, and high-visibility headings.
3. Confirm every English key and placeholder multiset exists in both targets and every route-driving term produces a nonblank ASCII-folded slug.
4. Verify French one/other behavior for 0, 1, and 2 and verify Spanish/English behavior for the same values in T10.

## T5 — Localize planning, routing, generated outputs, and render control

**ID:** T5 — Make `Language` an explicit value through the one website build path.

**Depends-on:** T1, T2, T4.

**Files:** `website/build.py:38-3224`.

**Assumptions:**

1. English URLs remain rooted and unchanged.
2. Semantic/category/country/subject paths localize; canonical entity components do not.
3. Source prose remains unchanged.
4. The website build performs no translation/label network work.
6. Closed lookups fail; institution labels fall back.
7. Stable page keys join locale siblings.
8. Identity, rank, membership, and ordering remain canonical.
9. Pure server number formatting changes presentation only.
10. Plurals use the locale code.
12. The root 404 remains English.
13. Provider code stays outside the builder.

**Steps → verify:**

1. Add the immutable language/catalogue value and load/validate all committed TOML after the single database read but before planning or staging.
2. Enforce exact English prefix/segments and source-equivalent English category/country/configured-subject slugs.
3. Keep canonical source names/control tokens separate from localized display labels throughout country, affiliation, subject, Explorer, map, facts, and share-card logic; never group, join, rank, or branch on translated text.
4. Route every current page family through language-owned segments, including nested country views, winner lists, people pagination, subject recent pages, institution-country pages, and all 10 map subject pages.
5. Add the complete stable key map from the spec to `PageJob`; require exactly one en/es/fr member per key and reject per-locale/cross-locale route or slug collisions before staging.
6. Build reciprocal alternate maps and classify share images from keys/templates rather than English route prefixes.
7. Localize titles, descriptions, breadcrumbs, facts, terms, ranking blurbs, JSON-LD display values, social descriptions/cards, and pure/thread-safe server number/plural formatting; English institution display always uses the recorded name.
8. Preserve raw canonical keys beside localized labels in Explorer/map/nearby payloads so filters, geo-IP matching, membership, and ranks do not change.
9. Generate root, Spanish, and French `llms.txt`; retain one root CSV/robots/sitemap; preserve current English share paths and write target-locale shares under locale directories.
10. Keep `render_error_page()` English with empty alternates. Make `build_home_page()` validate the same catalogues but rewrite only the English root homepage. Keep CLI completion counts truthful for the combined plan.
11. Retain current pre-promotion cleanup and existing `_promote()` semantics; do not claim or implement rollback-safe promotion in this feature.
12. Verify with T10 tests and `uv run ruff check website/build.py`; the actual build gate is T12.

## T6 — Localize site chrome and style the switcher

**ID:** T6 — Render language metadata/navigation consistently at every depth.

**Depends-on:** T5.

**Files:** `website/templates/base.html:1-71`; `website/static/style.css:57-91,852-910`.

**Assumptions:**

1. English root and `/es/`/`/fr/` prefixes are fixed.
7. The stable-key alternate map drives both `hreflang` and switching.
12. Root 404 is English.
14. The user's closed mobile navigation at `base.html:29` must survive.

**Steps → verify:**

1. Set the HTML language, localize chrome/metadata/accessibility/footer copy, and emit canonical plus reciprocal en/es/fr and English `x-default` alternates.
2. Build the switcher from the exact alternate map so it keeps the current stable page identity.
3. Handle empty alternates for root 404 without `StrictUndefined` failures.
4. Add compact switcher styles using current variables and responsive navigation; do not restore `open` on the mobile details element.
5. Verify via T10 rendered-page assertions at root and deep routes, 404 rendering, and a source diff proving line 29 stays closed.

## T7 — Localize server-rendered page templates

**ID:** T7 — Move non-browser page UI to catalogue lookups.

**Depends-on:** T5.

**Files:** `website/templates/index.html:1-120`; `website/templates/awards.html:1-9`; `website/templates/_awards.html:1-21`; `website/templates/prize.html:1-48`; `website/templates/winners.html:1-30`; `website/templates/category.html:1-28`; `website/templates/year.html:1-31`; `website/templates/winner.html:1-64`; `website/templates/person.html:1-33`; `website/templates/people.html:1-26`; `website/templates/_view_tabs.html:1-18`; `website/templates/countries.html:1-20`; `website/templates/country.html:1-22`; `website/templates/affiliation_countries.html:1-22`; `website/templates/affiliation_country.html:1-29`; `website/templates/affiliations.html:1-44`; `website/templates/affiliation.html:1-43`; `website/templates/universities.html:1-34`; `website/templates/university_countries.html:1-34`; `website/templates/subjects.html:1-21`; `website/templates/subject.html:1-27`; `website/templates/subject_affiliations.html:1-29`; `website/templates/subject_recent.html:1-34`.

**Assumptions:**

2. Display terms and relevant slugs localize; proper-name slugs do not.
3. Motivations, notes, institution descriptions, people, units, and cities remain source text.
6. Required UI/terms never silently fall back.
8. Membership and ordering remain canonical.
9. Dates remain ISO.
11. Person-facing copy is gender-neutral.

**Steps → verify:**

1. Replace every visible English UI literal, plural branch, table/control/accessibility label, and generated link phrase with catalogue output from T5.
2. Render translated prize/category/country/subject/laureate-type terms and exact-QID institution labels without using display strings for conditions such as the birth-country fact class.
3. Keep motivations, biographical notes, institution descriptions, names, units, cities, identifiers, brands, official URLs, and registry names unchanged.
4. Localize the wrapper of the Ask-AI query while retaining cited source text; keep all query construction escaped.
5. Verify via T10 snapshots/assertions for every template family, byte-equal excluded prose, and no required bare English UI in Spanish/French output.

## T8 — Localize Explorer, map, and nearby browser UI safely

**ID:** T8 — Translate runtime interactions without changing their data joins.

**Depends-on:** T5.

**Files:** `website/templates/explorer.html:1-658`; `website/templates/map.html:1-477`; `website/templates/nearby.html:1-148`.

**Assumptions:**

3. Names, cities, motivations, and other excluded source data remain unchanged.
6. Missing browser UI strings fail preflight.
8. Rankings, membership, and ordering remain canonical.
9. Runtime numbers use the page locale without changing values.
10. Runtime plurals use `Intl.PluralRules`.

**Steps → verify:**

1. Replace HTML copy, controls, help/error/privacy text, chart labels, popups, tooltips, result rows, and all accessibility text with catalogue strings.
2. Emit browser strings once as `<script type="application/json">` using `<`-safe JSON; parse them as data and interpolate only validated `{field}` placeholders.
3. Insert catalogue output through DOM text/attribute APIs; remove any path that places catalogue strings in `innerHTML`, executable source, `eval`, or `Function`.
4. Keep canonical country/subject/record keys and localized display labels separately; preserve Explorer geo-IP alias matching, map filters, payload indexes, nearby routes, and server rank order.
5. Use `Intl.NumberFormat(language.code)` and `Intl.PluralRules(language.code)` for runtime output and locale-aware sorting only for translated display labels.
6. Verify in T10 by parsing each JSON payload, syntax-checking built scripts, exercising representative success/error states, testing malicious `<script>` catalogue text, and comparing English versus localized record selections/ranks.

## T9 — Localize editorial About copy and keep root 404 compatible

**ID:** T9 — Translate long-form site copy and the English error document.

**Depends-on:** T5.

**Files:** `website/templates/about.html:1-170`; `website/templates/404.html:1-17`.

**Assumptions:**

3. Source dataset prose is excluded, but authored website editorial copy is translated.
6. Required UI copy fails on a miss.
12. The one root 404 remains English.

**Steps → verify:**

1. Replace all About editorial copy, headings, totals, link phrases, and accessibility text with catalogue values while preserving brand/license/official-link identities.
2. Replace 404 literals with catalogue lookups that render from the English language object and empty alternates.
3. Verify About renders in all three plans, 404 renders once at root, and no locale-specific server error behavior is introduced.

## T10 — Extend focused tests

**ID:** T10 — Prove catalogue, authoring, routing, rendering, and compatibility contracts.

**Depends-on:** T2, T3, T4, T5, T6, T7, T8, T9.

**Files:** `tests/test_build_website.py:135-2475`.

**Assumptions:** all 14 assumptions from the specification, including English URL stability, source-prose preservation, offline build behavior, canonical ordering, English-only root 404, and preservation of the user's nav change.

**Steps → verify:**

1. Add catalogue parse/completeness, exact English route pinning, 10-subject coverage, plural/number, fallback, and format-field tests.
2. Add mocked authoring tests described in T2/T3, including byte-identical rollback and safe logs.
3. Add full stable-key parity, route collision, English manifest, localized nested-route, canonical ordering/membership, and home-only unaffected-file tests.
4. Add reciprocal canonical/`hreflang`/switcher tests for every page family and root 404 compatibility.
5. Add motivation/profile/unit/name/date byte-preservation and exact English institution-name tests.
6. Add browser JSON/escaping/injection, JS syntax, runtime locale, geo-IP/filter/join, success/error/accessibility, and rank-equivalence tests.
7. Add localized `llms.txt`, shared sitemap/CSV/robots, locale share-path, English share-path, and build-time network prohibition tests.
8. Verify `uv run python -m unittest tests/test_build_website.py` passes and `uv run ruff check tests/test_build_website.py` is clean.

## T11 — Update repository guidance

**ID:** T11 — Document the implemented authoring and build contract.

**Depends-on:** T5.

**Files:** `AGENTS.md:94-133` (repository root).

**Assumptions:**

1. English root and Spanish/French prefixes are fixed.
3. Source prose exclusions are permanent product rules.
4. Website builds are offline; authoring commands are explicit.
5. English is the catalogue source and target catalogues are committed.
12. Root 404 is English.

**Steps → verify:**

1. Document locale prefixes, localized semantic/category/country/subject routes, canonical proper-name routes, and `hreflang`/switcher behavior.
2. Document catalogue locations, reviewed-key regeneration, label and translation commands, source-prose exclusions, and the no-network builder guarantee.
3. Update `llms.txt`, share-image, sitemap/page-count, home-only, and 404 descriptions to match implementation.
4. Verify every named file/command exists and guidance does not claim rollback-safe promotion or branch use.

## T12 — Full regression and public-contract gate

**ID:** T12 — Verify the complete implementation without modifying source files.

**Depends-on:** T1-T11.

**Files:** none.

**Assumptions:** all 14 specification assumptions.

**Steps → verify:**

1. Capture the current English route/share-asset manifest, then run `uv run website/build.py --base-url https://example.org/awards/`.
2. Verify the build reports 16 prizes, 7,345 pages per locale, 22,035 sitemap page URLs, exactly three siblings per stable key, and one sitemap at the current snapshot.
3. Compare manifests: every prior English page and public English share path remains; no `/en/` route exists; CSV/robots paths remain shared.
4. Check reciprocal canonical/`hreflang`/switcher links, localized semantic routes, root/Spanish/French `llms.txt`, locale share assets, and the English root 404.
5. Prove motivations and excluded profile/unit/name/date content are byte-identical across siblings and ranks/membership match English.
6. Run `uv run python -m unittest tests/test_build_website.py` and confirm all tests pass.
7. Run `uv run ruff check website/build.py scripts/fetch_wikidata_labels.py scripts/translate_catalogue.py tests/test_build_website.py` and confirm it is clean.
8. Run the home-only path against the completed build and verify only `website/dist/index.html` changes.
9. Confirm the full and home-only build made no label-fetch or translation-provider request and `git status --short` contains no generated `website/dist/` state.
