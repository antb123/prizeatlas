# Website blog — TODO — 20261108

Spec: `docs/website_blog_20261108.md`. Run from `datasets/`. Every task is self-contained; read the spec's Assumptions block first.
Parallel-safe: B1, B3, B4, B6. Serial: B2 after B1; B5 after B3 and B4; B7 last.

Shared assumptions (copied from the spec):
1. Posts are hand-written HTML fragments in `website/blog/posts/YYYYMMDD-<slug>.html`; stdlib only.
2. Figures are static inline SVG, `fill`/`stroke` only `currentColor` or `none`; no script, no img.
3. Blog pages are pre-rendered and committed; `website/build.py` only copies them and adds routes.
4. Canonical base is hard-coded `https://prizeatlas.org/blog/`.
5. English only; the menu label is a catalogue key in all four catalogues.

---

## B1 — `scripts/build_blog.py` and `website/blog/blog.css`

Depends-on: none
Files: new `scripts/build_blog.py`, new `website/blog/blog.css`

Steps:

1. Write `scripts/build_blog.py` in the shape of `scripts/build_calendar.py` (docstring with usage, module constants, small
   functions returning strings, `main()`, `if __name__ == "__main__": main()`). Beazley style, 180-char lines, type hints.

   ```python
   #!/usr/bin/env python3
   """Lint website/blog/posts/*.html and render website/blog/<slug>/index.html and website/blog/index.html.

       uv run scripts/build_blog.py
   """
   import datetime
   import re
   from dataclasses import dataclass
   from html import escape
   from html.parser import HTMLParser
   from pathlib import Path

   BLOG_DIR = Path(__file__).resolve().parent.parent / "website" / "blog"
   POSTS_DIR = BLOG_DIR / "posts"
   BASE_URL = "https://prizeatlas.org/blog/"
   MAX_BYTES = 60 * 1024
   SLUG = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
   HTML_ELEMENTS = {"h1", "h2", "h3", "p", "a", "ul", "ol", "li", "dl", "dt", "dd", "strong", "em", "code", "sup", "cite",
                    "blockquote", "hr", "br", "figure", "figcaption", "table", "caption", "thead", "tbody", "tr", "th", "td"}
   SVG_ELEMENTS = {"svg", "g", "path", "rect", "circle", "line", "polyline", "polygon", "text", "tspan", "title"}
   VOID = {"br", "hr"}
   SVG_ATTRIBUTES = {"x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "width", "height", "d", "points", "transform", "fill",
                     "stroke", "stroke-width", "fill-opacity", "text-anchor", "font-size"}
   ATTRIBUTES = {"a": {"href"}, "p": {"class"}, "th": {"colspan", "rowspan", "scope"}, "td": {"colspan", "rowspan", "scope"},
                 "svg": {"viewbox", "role"}}


   @dataclass(frozen=True)
   class Post:
       date: datetime.date
       slug: str
       title: str
       lede: str
       body: str
   ```

2. `class Linter(HTMLParser)` (`convert_charrefs=True`). `__init__(self, path: Path)` stores the path and state: `stack: list[str]`,
   `top_level: int` (count of elements started at depth 0), `title`/`lede` text accumulators, `need_title: bool`.
   `fail(self, rule: str)` raises
   `SystemExit(f"posts/{self.path.name}:{self.getpos()[0]}: {rule}")`.
   - `check(tag, attrs)`: tag in `HTML_ELEMENTS | SVG_ELEMENTS` else fail `element {tag} not allowed`. Allowed attribute names are
     `ATTRIBUTES.get(tag, set())`, or `SVG_ATTRIBUTES` for SVG elements other than `svg`; any other name fails
     `attribute {name} not allowed on {tag}`. `fill`/`stroke` value not in `{"currentColor", "none"}` fails. `p` with `class` other
     than `lede` fails. `href` not starting `/` or `https://` fails. `svg` without `viewbox` or with `role != "img"` fails.
   - Opening order: when `self.stack` is empty at a start tag, increment `top_level`; element 1 MUST be `h1`, element 2 MUST be
     `p` with `class="lede"`; an `h1` or a `p class="lede"` anywhere else fails. A start tag while the top of the stack is `h1` or
     the lede `p` fails (`h1 and lede are text only`). Track the lede by pushing the marker `"p.lede"` instead of `"p"`.
   - `need_title`: set on `<svg>`; the next start tag MUST be `title` else fail `svg must start with title`; an `</svg>` while
     `need_title` fails the same.
   - `handle_starttag`: `check`; push unless in `VOID`.
   - `handle_startendtag`: tag MUST be in `SVG_ELEMENTS | VOID` else fail `self-closing <{tag}/> not allowed`; `check`; no push.
   - `handle_endtag`: tag in `VOID` fails; top of stack (with `"p.lede"` read as `p`) MUST equal tag else fail
     `</{tag}> does not match <{top}>`; pop.
   - `handle_data`: non-whitespace before the first element fails `text before h1`; append to `title`/`lede` when inside them.
   - `handle_comment`, `handle_decl`, `unknown_decl`, `handle_pi`: fail `comments, declarations and processing instructions not allowed`.
   - `close()` override: call `super().close()`, then a non-empty stack fails `<{top}> never closed`; `top_level < 2` fails
     `missing h1 or lede`.

3. `read_post(path: Path) -> Post`: name MUST be `YYYYMMDD-<slug>.html` (`len(stem) > 9 and stem[8] == "-"`), date from
   `datetime.datetime.strptime(stem[:8], "%Y%m%d").date()` (ValueError → `SystemExit("posts/<name>: bad date")`), slug `stem[9:]`
   MUST fullmatch `SLUG` and MUST NOT be `posts`. Feed the text to a `Linter`, `close()` it, return
   `Post(date, slug, title.strip(), lede.strip(), text)`.

4. `def nice(d: datetime.date) -> str: return f"{d.day} {d:%B %Y}"`.

5. `head(title, description, canonical, root, css)`: returns the `<head>` block: charset, viewport, `<title>`, description,
   robots `index, follow`, canonical, `og:site_name` PrizeAtlas, `og:type` (article for posts, website for the index),
   `og:title`, `og:description`, `og:url`, `twitter:card` summary, `<link rel="icon" href="{root}favicon.svg" type="image/svg+xml">`,
   `<link rel="stylesheet" href="{root}static/style.css">`, `<link rel="stylesheet" href="{css}">`. Every value through
   `escape(..., quote=True)`. Pass `og_type` as an argument.

6. `render_post(post) -> str`: `root = "../../"`. Body: `<header><a class="site-name" href="../../">PrizeAtlas</a></header>`,
   `<nav class="breadcrumbs" aria-label="Breadcrumb"><a href="../../">Home</a> / <a href="../">Blog</a> / {escape(title)}</nav>`,
   `<main><article><p class="date"><time datetime="{iso}">{nice}</time></p>{body}</article>`,
   `<p><a href="../">← All posts</a></p></main>`. `body` = fragment with `href="/` → `href="../../"` and `href='/` → `href='../../`.
   `<title>` text: `f"{title} | PrizeAtlas Blog"`. Canonical `BASE_URL + slug + "/"`, css `../blog.css`.

7. `render_index(posts) -> str`: root `"../"`, css `"blog.css"`, canonical `BASE_URL`, title `Blog | PrizeAtlas`, description
   `"Articles on the world's major science prizes and their laureates."`. Breadcrumb `Home / Blog`. One
   `<li><time datetime>{nice}</time> <a href="{slug}/">{escape(title)}</a><p>{escape(lede)}</p></li>` per post, newest first.

8. `main()`: `paths = sorted(POSTS_DIR.glob("*.html"))`; empty → `SystemExit("posts/: no posts")`. Read every post (lint gate),
   check slugs unique (`SystemExit("posts/<name>: duplicate slug <slug>")`), render every page into a dict
   `{Path: str}`, check each post page `len(html.encode()) <= MAX_BYTES` (`SystemExit("posts/<name>: page is N bytes, limit 61440")`).
   Only then write each file (`mkdir(exist_ok=True)` for slug dirs) and print `wrote <path>`.

9. Write `website/blog/blog.css` (no colours):

   ```css
   article { max-width: 65ch; }
   article .date { margin: 0; opacity: .75; }
   article h1 + .lede, .lede { font-size: 1.125rem; }
   figure { margin: 1.5rem 0; }
   figure svg { width: 100%; height: auto; }
   svg text { fill: currentColor; }
   figcaption { font-size: .9rem; margin-top: .5rem; }
   table { border-collapse: collapse; }
   th, td { padding: .25rem .5rem; text-align: left; border-bottom: 1px solid currentColor; }
   .posts { list-style: none; padding: 0; }
   .posts li { margin: 0 0 1.25rem; }
   ```
   Give the index `<ul class="posts">`.

Verify: `uv run ruff check scripts/build_blog.py` clean. With one throwaway post in `posts/`, `uv run scripts/build_blog.py` writes
`website/blog/<slug>/index.html` and `website/blog/index.html`; a second run makes no diff. Delete the throwaway post and its
generated dir before committing (`git status` clean for `website/blog/` except `blog.css`).

---

## B2 — `tests/test_build_blog.py`

Depends-on: B1
Files: new `tests/test_build_blog.py`

Steps: `unittest`, matching `tests/test_build_website.py` style. Import the module by path
(`importlib.util.spec_from_file_location("build_blog", Path(__file__).parent.parent / "scripts" / "build_blog.py")`). Each test
writes fixtures to a `tempfile.TemporaryDirectory()` and points `build_blog.POSTS_DIR`/`BLOG_DIR` there (save and restore in
`setUp`/`tearDown`). Valid fixture:

```html
<h1>Fixture title</h1>
<p class="lede">Fixture lede &amp; more.</p>
<h2>Part</h2>
<p>See <a href="/nobel-prize/">Nobel</a> and <a href="https://example.org/">source</a>.<br></p>
<figure><svg viewBox="0 0 320 40" role="img"><title>Bars</title><rect x="0" y="0" width="10" height="10" fill="currentColor"/></svg>
<figcaption>One bar.</figcaption></figure>
```

Tests:
- valid post: `main()` writes both files; post page contains `href="../../nobel-prize/"`, canonical
  `https://prizeatlas.org/blog/fixture/`, `<title>Fixture title | PrizeAtlas Blog</title>`, lede escaped as `&amp;`.
- index lists two posts newest first.
- one failing test per rule, asserting the `SystemExit` message contains the rule text: bad date `20261340-x.html`; slug `posts`;
  text before h1; missing lede; link inside h1; `<script>`; `<div>`; `style=` attribute; `fill="#f00"`; svg without title;
  `href="http://x"`; unclosed `<strong>`; `<p/>`; `<!-- draft -->`; empty `posts/`; page over `MAX_BYTES`; duplicate slug.
- a failing lint writes nothing (target dir unchanged).

Verify: `uv run --with pytest pytest tests/test_build_blog.py` passes.

---

## B3 — `website/build.py`

Depends-on: none
Files: `website/build.py:4046-4050` (add after), `:4603`, `:4672-4673`

Steps:
1. After `write_calendar()` (ends `:4050`) add:

   ```python
   def write_blog(output: Path, website_dir: Path, routes: set[str]) -> list[str]:
       """Copy the pre-rendered blog (scripts/build_blog.py) to /blog/ and return its routes."""
       if "/blog/" in routes:
           raise SystemExit("website build: /blog/ is a planned route and collides with the pre-rendered blog")
       source = website_dir / "blog"
       shutil.copytree(source, output / "blog", ignore=shutil.ignore_patterns("posts"))
       return ["/blog/", *(f"/blog/{path.stem[9:]}/" for path in sorted((source / "posts").glob("*.html")))]
   ```
2. In `render_error_page`, after `href=lambda target: root + target.lstrip("/"),` (`:4603`) add
   `asset_href=lambda target: root + target,`.
3. At `:4672-4673` replace with:

   ```python
           calendar_routes = write_calendar(staging, website_dir)
           blog_routes = write_blog(staging, website_dir, {job.route for job in plan.jobs})
           write_sitemaps(staging, [*(job.route for job in plan.jobs), *calendar_routes, *blog_routes], normalized_base_url)
   ```

Verify: `uv run ruff check website/build.py` clean (B5 runs the tests).

---

## B4 — menu link and catalogues

Depends-on: none
Files: `website/templates/base.html:41`, `website/i18n/en.toml:38`, `website/i18n/es.toml:5,107`, `website/i18n/fr.toml:5,107`,
`website/i18n/ja.toml:107`

Steps:
1. `base.html`: after line 41 (`explorer` link) add
   `      <a href="{{ asset_href('blog') }}/">{{ t("chrome.blog") }}</a>`.
2. After each `"chrome.explorer"` line add: `en.toml` `"chrome.blog" = "Blog"`; `es.toml` `"chrome.blog" = "Blog"`;
   `fr.toml` `"chrome.blog" = "Blog"`; `ja.toml` `"chrome.blog" = "ブログ"`.
3. In the `reviewed = [...]` list on line 5 of `es.toml` and `fr.toml`, insert `"ui.chrome.blog"` in sorted position (before
   `"ui.chrome.breadcrumb"`). Leave `ja.toml` `reviewed = []` unchanged.

Verify: `uv run website/build.py --base-url https://example.org/awards/ --home-only` completes, which proves catalogue coverage.
The full build also needs B3 (the 404 page's `asset_href`).

---

## B5 — `tests/test_build_website.py`

Depends-on: B3, B4
Files: `tests/test_build_website.py:59`, `:1353-1356`, `:1595` area, `:2695`

Steps:
1. After the calendar copy at `:59`, write a minimal fixture blog:

   ```python
           blog = self.website / "blog"
           (blog / "posts").mkdir(parents=True)
           (blog / "posts" / "20261110-fixture.html").write_text('<h1>Fixture</h1>\n<p class="lede">Fixture.</p>\n')
           (blog / "fixture").mkdir()
           (blog / "fixture" / "index.html").write_text("<!doctype html><title>Fixture</title>")
           (blog / "index.html").write_text("<!doctype html><title>Blog</title>")
   ```
2. `:1354` and `:2695`: `len(plan.jobs) + 2` → `len(plan.jobs) + 4`; update the `:2695` comment to
   `# two calendar pages and two blog pages are not planned jobs`. Next to `:1355-1356` add
   `self.assertIn("https://example.org/awards/blog/", locations)` and
   `self.assertIn("https://example.org/awards/blog/fixture/", locations)`.
3. Near `:1595` (where `error_page` is read) add `self.assertIn('blog/">Blog</a>', error_page)`.
4. Add one test that a planned page links the blog: read any `dist/es/` page and assert `'blog/">Blog</a>'` is present.

Verify: `uv run --with pytest pytest tests/test_build_website.py` passes.

---

## B6 — `AGENTS.md`

Depends-on: none
Files: `../AGENTS.md` after `:148` (the calendar bullet)

Steps: add

```markdown
- The blog (`/blog/`, English only) is pre-rendered like the calendar: posts are HTML fragments in
  `website/blog/posts/YYYYMMDD-<slug>.html`, `uv run scripts/build_blog.py` lints them and writes `website/blog/<slug>/index.html`
  and `website/blog/index.html` (committed), and `write_blog()` in `website/build.py` copies them to `dist/blog/` and adds them to
  the sitemap. Lint rules and the author guide are in `docs/website_blog_20261108.md`. Figures are inline SVG only; no script.
  A renamed post leaves its old generated directory behind — `git rm` it. `--home-only` links to `/blog/` but does not copy it.
```

Verify: the bullet sits inside "static awards website", before "data explorer".

---

## B7 — end-to-end

Depends-on: B1-B6, and one real post from the owner in `website/blog/posts/`
Files: none new

Steps → verify:
1. `uv run scripts/build_blog.py` → prints `wrote` lines; rerun → `git diff --stat website/blog/` empty.
2. `uv run --with pytest pytest tests/test_build_blog.py tests/test_build_website.py` → passes.
3. `uv run website/build.py --base-url https://example.org/awards/` → succeeds; `dist/blog/index.html` and
   `dist/blog/<slug>/index.html` exist; `dist/404.html` and `dist/es/index.html` contain the Blog link; the sitemap lists both
   blog URLs.
4. `uv run ruff check scripts/build_blog.py website/build.py` → clean.
