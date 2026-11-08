# Country-scoped navigation

Status: implemented 20261108. The country timeline (`/countries/{country}/timeline/`) shipped alongside as a separate page linked from each view, not as a fourth tab.

## Problem

On `/countries/japan/`, clicking Awarded opens the global country ranking. Tabs must retain the selected country.

## Required behavior

- Keep the labels **Born**, **Awarded**, and **Died**.
- Awarded means the recipient lived in the country when the award was given, or was affiliated with an institution there. It does not mean ceremony location or nationality.
- This is a navigation change: preserve existing membership rules, counts, and ordering. The current Awarded dataset uses recorded award-time affiliations; describe that evidence accurately and do not infer residence or add residence-based membership in this change.
- Country detail routes become `/countries/{country}/born/`, `/countries/{country}/awarded/`, and `/countries/{country}/died/`.
- Keep global rankings at `/countries/`, `/countries/awarded/`, and `/countries/died/`. Selecting a country preserves the ranking's view.
- Place the country heading above its tabs. Country tabs link only to that country's three views. Remove global Cities, Cities %, and Institutions links from this detail tab bar; retain them on the global indexes.
- Breadcrumbs: `Home / Countries / Japan / Awarded`. Japan links to its Born view; Countries and a separate “All countries” return link lead to the corresponding global ranking.
- Generate all three views for every country present in any of these rankings. A missing view shows “No recipients recorded for this view.” Keep all three tabs visible, with the current tab marked `aria-current="page"`.

```text
Home / Countries / Japan / Awarded
Japan
Born   [Awarded]   Died
Recipients with a recorded award-time affiliation in Japan.
...
← All countries
```

## Existing URLs and languages

- Preserve old `/countries/{country}/`, `/countries/awarded/{country}/`, and `/countries/died/{country}/` links with static redirect pages to their new equivalents, including a visible fallback link and the destination canonical URL. Exclude redirect pages from sitemaps.
- Apply the same structure to all four languages, preserving existing country-slug localization rules. Translate the new Born route segment for Spanish and French; Japanese retains canonical ASCII segments.
- Update internal links, canonical URLs, breadcrumbs, hreflang, language switches, sitemaps, and generated machine-reader guides to the new routes.
- Timeline is deferred: its population and events need a separate definition. No new overview, institution, or city pages in this change.

## Implementation locations

Line references are to the source at specification time.

| File | Changes |
|---|---|
| `datasets/website/build.py:1937` | Construct country-first detail routes in `plan_country_places`. |
| `datasets/website/build.py:2918` | In `plan_country_pages`, plan missing views, country-scoped navigation, breadcrumbs, and compatibility pages. |
| `datasets/website/build.py:3637` | Update `_localized_place_route` to country-before-view ordering, including explicit Born. |
| `datasets/website/build.py:4517` | Supply separate detail-tab destinations rather than global ranking destinations. |
| `datasets/website/templates/_view_tabs.html:11` | Retain the global macro; add a small country-detail tab macro. |
| `datasets/website/templates/country.html:4` | Show heading before detail tabs, empty-state text, and view-preserving return link; preserve city-page behavior. |
| `datasets/website/templates/country_redirect.html` (new) | Minimal static redirect, canonical, and fallback link. |
| `datasets/website/i18n/{en,es,fr,ja}.toml` | Add required route/copy keys and translations; preserve reviewed catalogue rules. |
| `datasets/tests/test_build_website.py` | Update route assertions and add focused navigation/compatibility checks. |

## Acceptance checks

- From Japan Born, Awarded opens Japan Awarded; Died opens Japan Died. No detail tab opens a global ranking.
- From global Awarded, Japan opens Japan Awarded; All countries returns to global Awarded.
- Old URLs resolve to the equivalent new view. A country lacking death records has a working empty Died page.
- Counts and recipient order remain unchanged; city pages and global navigation still work.
- Verify equivalent behavior in all languages, including deployment under a URL subpath, reciprocal hreflang, canonical URLs, and sitemap exclusion of redirects.
- Run focused website tests and the full four-language build. Database remains unchanged.
