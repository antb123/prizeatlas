# Shareable ranking cards — 20260729

## Goal and current state

Prize Atlas links must produce attractive 1200×630 previews in social networks, messaging apps, and AI answers without adding share buttons, icons, “Ask AI” text, or other in-page controls. The only visible page change is the qualified homepage institution section below.

Before this feature, `datasets/website/templates/base.html:9-15` supplied basic Open Graph fields and `twitter:card="summary"`, but no `og:image`. `datasets/website/static/` had no share assets, and page plans in `datasets/website/build.py` supplied no share context.

## Bounded image set

The live build must emit exactly 20 PNGs, not one per page:

- 14 `static/share/prize-{ranking.slug}.png` images, one per existing prize family;
- `static/share/laureates.png`, shared by `/people/` and every laureate detail page;
- `static/share/institutions.png`, shared by `/affiliations/` and every institution detail page;
- `static/share/universities.png`, shared by `/universities/` and its child pages;
- `static/share/map.png` for `/map/`;
- `static/share/nearby.png` for `/nearby/`;
- `static/share/default.png` for every other page, including the homepage and 404.

Generate these RGB PNGs directly with pinned Pillow during the existing atomic staging build. Pillow's pinned embedded default font is sufficient because only prize names and fixed English labels are drawn; this avoids browser automation, SVG conversion, subprocesses, host fonts, and a large bundled font.

Each prize image contains the prize name, its one-based position in `rankings`, `len(layout.records)`, distinct existing `AwardRecord.high_school_subject` values in site subject order, and `public_url(base_url, layout.route)`. The five shared section images contain fixed truthful section copy and the corresponding Prize Atlas section URL. Image generation failure must stop the build before promotion.

## Per-page metadata

Laureate and institution pages still expose individual ranking data even though their image is shared. Their `og:description` is produced from a small `ShareCard` context:

| Page | Rank | Award count | Subjects |
|---|---|---|---|
| Laureate | Position of the matching route in the existing `explorer_payload()["people"]` order. | Existing Explorer field `c`, the number of award rows. | Names already in `Laureate.subjects`. |
| Prize | Position in `rankings`, already ordered by `Ranking.score` descending. | `len(layout.records)`. | Distinct nonblank subjects in `layout.records`, in existing site subject order. |
| Institution | Position in `affiliations`, already ordered by laureate count then name. | Distinct `AwardLink.record.award_record_id` values in `Affiliation.awards`. | Names already in `Affiliation.subjects`. |

The description format is `TYPE rank #N. N recorded award(s). Subjects: ….` The existing canonical `og:url` supplies the exact page URL. The Explorer's default points comparator must retain server order as its final tie-break so its displayed laureate rank and metadata rank agree in every locale.

In `datasets/website/templates/base.html`, retain the existing tags and add `og:image`, `og:image:width=1200`, `og:image:height=630`, `twitter:image`, and `twitter:card=summary_large_image`. `_render_job` and `render_error_page` always supply absolute image URLs using the configured `--base-url`, including deployment subpaths.

`startdev.sh` must invoke `uv run website/build.py`, not `python -m website.build`, so uv reads the builder's inline Pillow dependency and adjacent lock.

## Homepage wording

`plan_home_page` supplies the first `HOMEPAGE_ROWS` already-ranked institutions. `datasets/website/templates/index.html` adds “Top Institutions”, headed **“Institutions with the most award-winning laureates”**, linked names with laureate counts, and an “All institutions” link.

Adjacent copy must state that the ranking uses affiliations recorded when an award was made and is not a measure of institutional quality. This preserves the item 12 wording **“Universities with the most award-winning laureates”**; “Top Universities” would incorrectly imply a quality ranking.

## Acceptance

- The live build produces exactly 20 share PNGs, all 1200×630, with no bundled font.
- Prize, laureate, institution, university, map, nearby, and fallback pages reference the expected reusable absolute image URL.
- Prize images contain their existing prize-specific rank, count, subjects, and URL; laureate and institution previews expose their individual values through `og:description`.
- A repeated institution award ID counts once; a locale-sensitive laureate tie matches the Explorer.
- Identical builds produce identical bytes and filenames, and no share control appears in page content.
- Run `cd datasets && uv run --with pillow==11.3.0 --with pytest -m pytest tests/test_build_website.py`, `uv run website/build.py --base-url https://example.org/awards/`, and `./startdev.sh`.
