# Website blog — 20261108

## Goals

Publish dated, English-only articles at `/blog/` (announcement write-ups, year-end roundups, data stories) that link into the
reference pages, with one fixed post structure that a linter enforces so every post looks and weighs the same on low-end phones.

## Background

- No blog has ever existed: no files, commits, or docs mention one (checked 20261108).
- The award calendar is the precedent this design copies. `website/calendar/events.toml` is hand-authored;
  `scripts/build_calendar.py` renders committed HTML into `website/calendar/<year>/index.html` with a hard-coded canonical base
  (`scripts/build_calendar.py:13`); `write_calendar()` in `website/build.py:4046-4050` copies the directory into `dist/` and
  returns its routes; `website/build.py:4672-4673` adds them to the sitemap. The calendar is English-only and localized pages
  link to it through `asset_href` (`website/templates/awards.html:8`).
- The main menu is `website/templates/base.html:34-42`; every label is a `ui.chrome.*` key (`website/i18n/en.toml:28-38`,
  `es.toml`/`fr.toml`/`ja.toml:107`). Coverage is closed: a `t()` key missing from any `[ui]` table fails the build.
- `base.html` is also rendered by the 404 page through `render_error_page` (`website/build.py:4579-4624`), which passes `href`
  (`:4603`) but no `asset_href`. The Jinja environment uses `StrictUndefined` (`:4372`), so a menu link that calls `asset_href`
  breaks every full build unless that function is added there.
- The site stylesheet `static/style.css` (18 KB, unhashed, `website/build.py:4545`) already carries the palette, typography and
  dark mode. Readers arriving from the site have it cached.
- The audience is low-end phones on metered data; page weight governs (memory: target-audience-african-phones).
- Owner decisions 20261108: English only; URL `/blog/`; posts are HTML fragments with linted structure; Blog link in the main menu
  for every language; figures are static inline SVG only — no JavaScript, no chart library, no data pipeline.

## Assumptions

1. **(load-bearing)** Posts are hand-written HTML fragments; no Markdown, no new dependency (stdlib `html.parser`).
2. **(load-bearing)** Figures are static inline `<svg>`, monochrome via `currentColor` so they follow dark mode; no `<script>`,
   no `<img>`, no external resources.
3. **(load-bearing)** Blog pages are pre-rendered by `scripts/build_blog.py` (not planned by `website/build.py`), but use the
   site stylesheet and wordmark so they read as the same site. They do not copy the full menu (it would drift).
4. The canonical base is hard-coded `https://prizeatlas.org/blog/`, as the calendar hard-codes its own (`build_calendar.py:13`);
   the sitemap uses `--base-url`. This mismatch already exists for the calendar and is accepted.
5. A post's date and slug come from its filename; its title and summary are the plain text of its `<h1>` and `<p class="lede">`.
6. Generated HTML is committed, as calendar output is; `website/build.py` only copies it.
7. Localized readers following the menu link land on the English blog, as they do for the calendar.
8. Editorial content is not part of this change, but it MUST NOT merge until one real post exists (rule 9 enforces it).

## Scope

| File | Action | Size |
|---|---|---|
| `scripts/build_blog.py` | new — lint posts, render post pages and the index | ~140 LOC |
| `website/blog/blog.css` | new — article rules on top of the site stylesheet | ~25 LOC |
| `website/blog/posts/YYYYMMDD-<slug>.html` | authored fragments | content |
| `website/blog/<slug>/index.html`, `website/blog/index.html` | generated, committed | — |
| `website/build.py:4046-4050` | add `write_blog()` after `write_calendar()` | ~8 LOC |
| `website/build.py:4603` | add `asset_href` to `render_error_page` | 1 LOC |
| `website/build.py:4672-4673` | call `write_blog()`; pass its routes to `write_sitemaps` | ~2 LOC |
| `website/templates/base.html:41` | Blog menu link after Explorer | 1 LOC |
| `website/i18n/en.toml:38`, `es.toml:107`, `fr.toml:107`, `ja.toml:107` | add `"chrome.blog"` | 4 LOC |
| `website/i18n/es.toml:5`, `fr.toml:5` | add `"ui.chrome.blog"` to `reviewed` | 2 edits |
| `tests/test_build_blog.py` | new — lint and render tests | ~80 LOC |
| `tests/test_build_website.py:59`, `:1354`, `:2695`, new 404 assertion | fixture blog, sitemap counts, 404 link | ~15 LOC |
| `../AGENTS.md:146-148` | blog bullet under "static awards website" | ~6 lines |

New files: 3 plus posts and generated output. Modified files: 8.

## Data flow

```text
website/blog/posts/YYYYMMDD-<slug>.html            (hand-written fragment)
        │
        ▼  uv run scripts/build_blog.py
   lint every post ── first violation → exit 1 "path:line: rule", nothing written
        │ all pass
        ▼
website/blog/<slug>/index.html, website/blog/index.html   (committed)
        │
        ▼  uv run website/build.py --base-url …
write_blog(): refuse if /blog/ is a planned route → copytree website/blog → dist/blog (ignore posts/)
              → routes from posts/ filenames → write_sitemaps
```

## Post format

One file per post: `website/blog/posts/YYYYMMDD-<slug>.html`. The filename date is the publication date; `/blog/<slug>/` is the URL.

```html
<h1>2026 science laureates: where they were born</h1>
<p class="lede">Plain text, no links. Used as the meta description and the index summary.</p>
<h2>Physics</h2>
<p>Francis Halzen … <a href="/nobel-prize/">Nobel Prize</a></p>
<figure>
  <svg viewBox="0 0 320 120" role="img"><title>Laureates by birth country</title>
    <text x="0" y="14" font-size="12">United States</text>
    <rect x="110" y="4" width="180" height="12" fill="currentColor" fill-opacity="0.6"/>
  </svg>
  <figcaption>Birth countries of the 2026 laureates: United States 9, Germany 3, Japan 2.</figcaption>
</figure>
<h2>Sources</h2>
<ul><li><a href="https://www.nobelprize.org/">nobelprize.org</a></li></ul>
```

Author guide (not linted): internal links are written site-root (`/nobel-prize/`) and the renderer makes them relative; SVG text
at least 12 units in a 320-unit viewBox; labels left, bars right; state the key figures in the caption or body, because
`role="img"` hides them from screen readers; for fewer than ten values prefer a `<table>`; end data stories with `## Sources`.

## Lint rules

`scripts/build_blog.py` MUST lint every post before writing anything and MUST stop at the first violation with
`raise SystemExit("posts/<file>:<line>: <rule>")`, as `build_calendar.py` does for unknown prizes. Rules:

1. **Name.** Filename is `YYYYMMDD-<slug>.html`; `datetime.strptime(name[:8], "%Y%m%d")` MUST succeed; slug MUST match
   `[a-z0-9]+(-[a-z0-9]+)*`, MUST be unique, and MUST NOT be `posts`.
2. **Opening.** Text MUST sit inside an element (none before `<h1>`, none between top-level blocks). The `<h1>` is the only one and the first element; the next element
   is the only `<p class="lede">`. Both MUST contain text only, no child elements.
3. **Elements** (closed list). HTML: `h1 h2 h3 p a ul ol li dl dt dd strong em code sup cite blockquote hr br figure figcaption
   table caption thead tbody tr th td`. SVG: `svg g path rect circle line polyline polygon text tspan title`.
4. **Attributes** (closed list, per element; `html.parser` lowercases names): `a`: `href`; `p`: `class="lede"` only;
   `th`/`td`: `colspan rowspan scope`; `svg`: `viewbox role`; other SVG elements: `x y x1 y1 x2 y2 cx cy r width height d points
   transform fill stroke stroke-width fill-opacity text-anchor font-size`. `fill` and `stroke` MUST be `currentColor` or `none`.
5. **SVG.** Every `<svg>` MUST have `viewbox` and `role="img"`, and its first element child (whitespace skipped) MUST be `<title>`.
6. **Links.** `href` MUST start with `/` (internal) or `https://`.
7. **Nesting.** The linter keeps its own open-element stack: a start tag pushes, an end tag MUST match the top. `br` and `hr` are
   the only HTML void elements; the self-closing form (`<x/>`) is allowed only for SVG elements, `br` and `hr`. The stack MUST be
   empty at end of file.
8. **No hidden content.** Comments, `<!doctype>`, `<![CDATA[` and processing instructions MUST fail.
9. **Not empty.** The run MUST fail when `posts/` holds no post.
10. **Weight.** Each generated post page MUST be at most 60 KB, measured as UTF-8 bytes of the written file.

## Rendering

`scripts/build_blog.py` mirrors `scripts/build_calendar.py`: module constants (`BLOG_DIR`, `BASE_URL`), small functions that return
strings, one `main()` that prints one line per file written.

- **Post page** `website/blog/<slug>/index.html`:
  - Head: doctype, `lang="en"`, charset, viewport, `<title>{h1} | PrizeAtlas Blog</title>`, meta description = lede, robots
    `index, follow`, canonical `BASE_URL + slug + "/"`, `og:site_name` PrizeAtlas, `og:type` article, `og:title`,
    `og:description`, `og:url`, `twitter:card` summary, favicon `../../favicon.svg`, stylesheets `../../static/style.css` then
    `../blog.css`.
  - Body: header with the PrizeAtlas wordmark linking `../../`, breadcrumb `Home / Blog / {h1}` (Blog links `../`), `<article>`
    holding `<p class="date"><time datetime="YYYY-MM-DD">10 November 2026</time></p>` then the fragment, then a footer link
    `← All posts` to `../`.
  - The fragment is emitted verbatim except internal links: `href="/` becomes `href="../../`, so links survive a subpath
    `--base-url` like every other page (`website/build.py:619-637`).
  - `{h1}` and the lede are unescaped from the fragment and re-escaped with `html.escape` wherever they appear in the head.
- **Index** `website/blog/index.html`: same head with paths one level shallower (`../favicon.svg`, `../static/style.css`,
  `blog.css`), canonical `BASE_URL`; one `<li>` per post, newest first: visible date, title link `<slug>/`, lede.
- `blog.css` holds only what the site stylesheet lacks: `article{max-width:65ch}`, lede at `1.125rem`, `figure svg{width:100%;
  height:auto}`, `svg text{fill:currentColor}`, table and `figcaption` spacing. No colours of its own.
- Generated directories are not pruned. A renamed or deleted post leaves its old `website/blog/<slug>/` behind, visible in
  `git status`; delete it with `git rm`. Routes come from post filenames, so an orphan never reaches the sitemap.

## Website build

- `write_blog(output, website_dir, routes) -> list[str]` after `write_calendar()` at `website/build.py:4050`:
  - `raise SystemExit("…/blog/ is a planned route…")` if `"/blog/"` is in `routes` (planned job routes), instead of a bare
    `FileExistsError` from `copytree`.
  - `shutil.copytree(website_dir / "blog", output / "blog", ignore=shutil.ignore_patterns("posts"))`.
  - Return `"/blog/"` plus `f"/blog/{name[9:-5]}/"` for each file in `website_dir / "blog" / "posts"`, sorted.
- `website/build.py:4672-4673`: `blog_routes = write_blog(staging, website_dir, {job.route for job in plan.jobs})`; pass
  `*blog_routes` to `write_sitemaps`.
- `website/build.py:4603`: add `asset_href=lambda target: root + target` to `render_error_page`, so the 404 renders the menu.
- `website/templates/base.html:41`: `<a href="{{ asset_href('blog') }}/">{{ t("chrome.blog") }}</a>` after Explorer.
- Catalogues: `"chrome.blog" = "Blog"` in the `[ui]` table of `en.toml`, `es.toml`, `fr.toml`; `"ブログ"` in `ja.toml`. Add
  `"ui.chrome.blog"` to `reviewed` in `es.toml` and `fr.toml`. `ja.toml` has `reviewed = []`, so `translate_catalogue.py ja`
  may regenerate the label, as it does every other Japanese key.
- `--home-only` rewrites only the home page, so its new Blog link is dead until a full build has written `dist/blog/`. Document
  this in `AGENTS.md`; no code change.

## Behavior

### Requirement: lint gate — the generator MUST write nothing when any post violates a rule
#### Scenario: script tag
- WHEN  a post contains `<script>`
- THEN  `build_blog.py` exits 1 with `posts/<file>:<line>: element script not allowed`
- AND   no file under `website/blog/` changes

#### Scenario: unclosed element
- WHEN  a post opens `<strong>` and never closes it
- THEN  the run fails naming that file and line

### Requirement: publish — a valid post MUST appear on its page, the index and the sitemap
#### Scenario: new post
- WHEN  a valid post `posts/YYYYMMDD-<slug>.html` exists and both builders run
- THEN  `dist/blog/<slug>/index.html` exists, its internal links are relative, and its canonical is `BASE_URL + slug + "/"`
- AND   `dist/blog/index.html` lists it newest first, and the sitemap contains `/blog/` and `/blog/<slug>/`

### Requirement: menu — every page in every language, including the 404, MUST link to the English blog
#### Scenario: Spanish page and 404
- WHEN  a reader opens any `/es/` page or the root `404.html`
- THEN  the main menu shows the catalogue's Blog label linking to the root `/blog/`

## Tests

- `tests/test_build_blog.py`: one valid fixture post renders; each of rules 1-10 has one failing fixture asserting the message;
  internal `href="/x/"` becomes `href="../../x/"`; the index orders newest first.
- `tests/test_build_website.py:59`: write a minimal fixture `website/blog/` (one post page, `index.html`, `posts/` with one file)
  instead of copying the real directory, so counts do not move with every published post.
- `tests/test_build_website.py:1354` and `:2695`: expected sitemap count becomes `len(plan.jobs) + 2 + 2` (calendar pages plus
  `/blog/` and the fixture post), with asserts for both blog URLs next to `:1355-1356`.
- New assertion near `:1595`: `dist/404.html` contains the Blog link.

## Verification

- `uv run scripts/build_blog.py` writes the pages; a second run produces no diff.
- `uv run --with pytest pytest tests/test_build_blog.py tests/test_build_website.py` passes.
- `uv run website/build.py --base-url https://example.org/awards/` succeeds and `dist/blog/` exists.
- `uv run ruff check scripts/build_blog.py` is clean.

## Out of scope

Feed (RSS/Atom); translated posts; JavaScript or interactive charts; images and per-post share images (`og:image`); tags,
categories, pagination; comments; JSON-LD; an `llms.txt` entry (needs a key in all four catalogues); validating internal links
against built routes; pruning orphaned generated directories; the full site menu on blog pages.
