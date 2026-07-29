# Shareable ranking cards — 20260729

## Goal and current state

Prize Atlas laureate, prize, and institution detail links must produce an attractive 1200×630 preview in social networks, messaging apps, and AI answers. This is metadata-only on those pages: no share button, icon, “Ask AI” text, or other visible control. The one visible change is the homepage section described below.

Before this feature, `datasets/website/templates/base.html:9-15` supplied `og:site_name`, `og:type`, title, description, URL, and `twitter:card="summary"`, but no `og:image`. `datasets/website/static/` held the favicon, logos, and stylesheet, with no share image or generator. `datasets/website/build.py:1474-1516,1667-1700,1939-1983` planned the relevant pages and `datasets/website/build.py:2586-2616` copied static assets and rendered those plans.

“Winner” below means a merged laureate page rendered from `person.html`, not an individual award-record page rendered from `winner.html`.

## Card contract

Every specific card shows the page name, a labelled one-based rank, “recorded award(s)”, subjects, and the absolute canonical Prize Atlas URL. No new data or ranking is derived:

| Page | Existing source for rank | Existing source for award count | Existing source for subjects and URL |
|---|---|---|---|
| Laureate | Position of the matching route in `explorer_payload()["people"]`, whose existing order is points descending, award count descending, then server-side name order (`datasets/website/build.py:462-548`). `create_site_plan` computes this payload once; `plan_person_pages` matches `relative_route(EXPLORER_ROUTE, person.route)`. | Explorer field `c`, already the number of the laureate's award rows. | Subject names in `Laureate.subjects`; `public_url(base_url, person.route)` and the existing person slug. |
| Prize | Position in `rankings`, already ordered by `Ranking.score` descending in `create_site_plan` (`datasets/website/build.py:2229-2259`). | `len(layout.records)` from `PrizeLayout.records`. | Distinct nonblank `AwardRecord.high_school_subject` values, ordered by the existing site-wide subject order; `public_url(base_url, layout.route)` and `Ranking.slug`. |
| Institution | Position in `affiliations`, already ordered by laureate count then name in `plan_affiliations` (`datasets/website/build.py:1045-1110`). | Count of distinct `AwardLink.record.award_record_id` values in `Affiliation.awards`. Distinct IDs avoid counting one award twice when two affiliation entries resolve to the same parent. | Subject names in `Affiliation.subjects`; `public_url(base_url, affiliation.route)` and `Affiliation.slug`. |

The Explorer's default points comparator in `datasets/website/templates/explorer.html:248-258` must preserve the payload's server order as its final tie-break. This keeps the visible rank and laureate card rank identical across browser locales.

## Image production and files

Generate RGB PNGs directly with pinned Pillow during the existing atomic staging build. This is the simplest reliable social-card format that fits the Python builder: it avoids browser automation, SVG conversion, subprocesses, and a second publication path while adding only one image dependency.

The renderer loads the repository-owned `datasets/website/static/fonts/noto-sans-cjk.ttc`, so output is deterministic and names already containing CJK characters render correctly; its redistribution notice lives beside it. It must wrap long text, treat dataset values as text rather than markup, and fail the build before promotion if the font or image generation fails.

Generated files are not committed and land in `datasets/website/dist/static/share/`:

- `winner-{person-slug}.png`
- `prize-{ranking.slug}.png`
- `institution-{affiliation.slug}.png`
- `default.png`

`default.png` shows the Prize Atlas identity, site description, and configured base URL. It is used for the homepage, list pages, individual award-record pages, 404 page, and every other page without a specific card.

## Metadata and planner wiring

In `datasets/website/templates/base.html:9-15`, retain the existing tags and add:

- `og:image` from `share_image`;
- `og:image:width` from `share_image_width` (`1200`);
- `og:image:height` from `share_image_height` (`630`);
- `twitter:image` from `share_image`;
- `twitter:card` with fixed value `summary_large_image`.

`_render_job` and `render_error_page` in `datasets/website/build.py:2488-2556` must always supply the exact context keys `share_image`, `share_image_width`, and `share_image_height`. `share_image` is an absolute `public_url`, including any `--base-url` deployment subpath. The prize, laureate, and institution planners supply a `ShareCard`; the common renderer maps its type and existing slug to the specific filename, otherwise selecting the fallback.

Expected versioned changes are limited to `website/build.py`, its script lock, `templates/base.html`, `templates/index.html`, `templates/explorer.html`, `templates/affiliation.html`, the two font files, and focused coverage in `tests/test_build_website.py`. There is no database, schema, route, sitemap, stylesheet, visible sharing control, or committed `dist/` change.

## Homepage wording

`plan_home_page` receives the already ranked institutions and supplies `top_institutions=tuple(affiliations[:HOMEPAGE_ROWS])`. `datasets/website/templates/index.html:16-49` adds “Top Institutions”, headed **“Institutions with the most award-winning laureates”**, up to eight linked names with their existing `Affiliation.count` laureate counts, and an “All institutions” link.

Adjacent copy must state that the ranking uses affiliations recorded when an award was made and is not a measure of institutional quality. This resolves the tension with `todo.md` item 12: “Top Institutions” is promotional shorthand, but the university ranking must remain **“Universities with the most award-winning laureates”** because award-time affiliation does not measure university quality.

## Acceptance

- Representative laureate, prize, and institution pages reference existing 1200×630 specific PNGs through absolute `og:image` and `twitter:image` URLs and use `summary_large_image`.
- The three card types use exactly the ranks, counts, subjects, and URLs defined above; a locale-sensitive name tie and a repeated institution award ID cover the two counting risks.
- A non-card page and `404.html` use the same fallback, and identical builds produce identical image bytes and filenames.
- The homepage uses the qualified institution wording and adds no “Top Universities” shorthand; no share control appears anywhere.
- Run `cd datasets && uv run --with pillow==11.3.0 --with pytest -m pytest tests/test_build_website.py`, then `uv run website/build.py --base-url https://example.org/awards/`. After deployment, check one URL of each specific type and one fallback page in representative share clients.
