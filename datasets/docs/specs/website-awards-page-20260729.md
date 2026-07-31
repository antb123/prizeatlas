# Dedicated awards page — 20260729

## Goals

The top navigation MUST label the award-family index **Awards** and link to a dedicated `/awards/` page. That page MUST list every award family shown on the homepage—14 with the current `award_ranking` data—while the homepage remains unchanged.

Success means a build writes `website/dist/awards/index.html`, includes `/awards/` in the sitemap, and renders deployment-relative Awards links from normal pages and `404.html`.

## Background

`website/templates/base.html:21-33` currently labels the first navigation link “Prizes” and sends it to `home_href`. `website/templates/index.html:1-75` combines the editorial homepage introduction, totals, “Most decorated”, “Recently awarded”, and the award-family list.

`website/build.py:2036-2088` plans the homepage and passes `prizes=tuple((ranking, prize_routes[ranking.qid]) ...)` to `index.html`. The rankings are already loaded, validated, and sorted by score in `website/build.py:2225-2236`; the current database supplies 14 rankings. No new query or data model is needed.

## Assumptions

1. **Load-bearing:** “All 14” means every entry in the existing `rankings` list, not a hard-coded count or allowlist.
2. **Load-bearing:** “Stripped copy” means the homepage and new page render one shared `ranked-awards` partial, while the new page excludes the introduction, totals, “Most decorated”, and “Recently awarded”.
3. The new page retains each award card's rank, logo, name, prize-page link, official-site link, blurb, score, and score bar.
4. The new page preserves the homepage tuple order; changing award ordering is not part of this change.
5. The header site name at `website/templates/base.html:22` remains a home link.

## File-by-file changes

| File | Current lines | Required change |
|---|---:|---|
| `website/templates/base.html` | 21-33 | Change the nav label from `Prizes` to `Awards` and resolve its href with `href(awards_route)` instead of `home_href`. Leave the site-name home link unchanged. |
| `website/templates/index.html` | 49-74 | Replace the inline `ranked-awards` markup with the shared `_awards.html` include; generated homepage output must not change. |
| `website/templates/_awards.html` | new file | Hold the existing `index.html:49-74` section unchanged so both pages render the same award cards. |
| `website/templates/awards.html` | new file | Extend `base.html` and include only `_awards.html`. |
| `website/build.py` | 42-70, 71-96 | Register `awards.html` and `_awards.html` in `TEMPLATES` and define `AWARDS_ROUTE = "/awards/"`. |
| `website/build.py` | 2036-2088, 2215-2269 | Add a small Awards-page planner beside `plan_home_page`, using the same `rankings` and `prize_routes` to pass the existing `prizes` tuple. Add its `PageJob` to `create_site_plan`; the job route is `/awards/`, its template is `awards.html`, and it has neutral title/description metadata and no breadcrumbs. Existing job rendering will write `website/dist/awards/index.html` and include the route in sitemap generation. |
| `website/build.py` | 2473-2503, 2509-2537 | Supply `awards_route=AWARDS_ROUTE` to both ordinary page rendering and `404.html` rendering so `StrictUndefined` succeeds and the nav link remains deployment-relative everywhere. |
| `tests/test_build_website.py` | 492-567, 1491-1522 | Extend the complete-build assertions to verify the output route, sitemap entry, all fixture award links, absence of homepage-only/ranking copy on the Awards page, unchanged homepage content, and relative nav links from root, nested, and 404 pages. |

Expected implementation scope: 6 files, including two new templates, and approximately 45-70 changed or added implementation/test lines.

## Required behavior

- `/awards/` MUST render exactly one entry per `Ranking`; with current production data that is 14 entries.
- The Awards nav link MUST resolve correctly under a deployment subpath and from nested routes.
- The new page MUST NOT contain “Prestigious Awards and Winners”, “An editorial ranking”, “Most decorated”, “Recently awarded”, or totals. Both pages MUST render the same shared `ranked-awards` partial.
- `/` MUST continue rendering `website/templates/index.html` exactly as it does before this change, including its editorial content and ranked-awards section.
- The implementation MUST NOT hard-code 14; additions or removals in `award_ranking` must flow to both pages through the existing planner data.

Verification SHALL run from `datasets/`:

`uv run python -m unittest tests.test_build_website.WebsiteBuildTests`

It SHALL also build with `uv run website/build.py --base-url https://example.org/awards/` and confirm `website/dist/awards/index.html`, canonical URL `https://example.org/awards/awards/`, and the matching sitemap entry.

## Out of scope

Do not change the rendered homepage, ranking data, prize detail routes, `website/static/style.css`, `about.html`, `llms.txt`, or generated `website/dist/` output. Do not change award ordering, scores, blurbs, homepage content, the site-name home link, or any database content or schema.
