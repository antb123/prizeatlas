#!/usr/bin/env python3
"""Lint website/blog/posts/*.html and render website/blog/<slug>/index.html and website/blog/index.html.

    uv run scripts/build_blog.py

A post is an HTML fragment named YYYYMMDD-<slug>.html. Rules and the author guide: docs/website_blog_20261108.md.
The first violation stops the run before anything is written.
"""
import datetime
import re
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from typing import NoReturn

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


class Linter(HTMLParser):
    """Enforce the post structure. Raises SystemExit naming file and line on the first violation."""

    def __init__(self, path: Path) -> None:
        super().__init__(convert_charrefs=True)
        self.path = path
        self.stack: list[str] = []
        self.top_level = 0
        self.title = ""
        self.lede = ""
        self.need_title = False

    def fail(self, rule: str) -> NoReturn:
        raise SystemExit(f"posts/{self.path.name}:{self.getpos()[0]}: {rule}")

    def check(self, tag: str, attrs: list[tuple[str, str | None]]) -> str:
        """Validate one start tag and return the marker it pushes on the stack."""
        if tag not in HTML_ELEMENTS | SVG_ELEMENTS:
            self.fail(f"element {tag} not allowed")
        if tag in SVG_ELEMENTS and tag != "svg" and "svg" not in self.stack:
            self.fail(f"element {tag} only allowed inside svg")
        if self.stack and self.stack[-1] in ("h1", "p.lede"):
            self.fail("h1 and lede are text only")
        if self.need_title and tag != "title":
            self.fail("svg must start with title")
        self.need_title = False

        values = dict(attrs)
        allowed = SVG_ATTRIBUTES if tag in SVG_ELEMENTS and tag != "svg" else ATTRIBUTES.get(tag, set())
        for name, value in attrs:
            if name not in allowed:
                self.fail(f"attribute {name} not allowed on {tag}")
            if name in ("fill", "stroke") and value not in ("currentColor", "none"):
                self.fail(f"{name} must be currentColor or none")
            if name == "href" and not (value or "").startswith(("/", "https://")):
                self.fail("href must start with / or https://")
            if name == "class" and value != "lede":
                self.fail('class allowed only as class="lede"')
        if tag == "svg":
            if "viewbox" not in values or values.get("role") != "img":
                self.fail('svg needs viewBox and role="img"')
            self.need_title = True

        lede = tag == "p" and values.get("class") == "lede"
        if not self.stack:
            self.top_level += 1
            if self.top_level == 1 and tag != "h1":
                self.fail("post must open with h1")
            if self.top_level == 2 and not lede:
                self.fail('h1 must be followed by p class="lede"')
        if tag == "h1" and self.top_level != 1:
            self.fail("only one h1, first")
        if lede and (self.stack or self.top_level != 2):
            self.fail("only one lede, straight after h1")
        return "p.lede" if lede else tag

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        marker = self.check(tag, attrs)
        if tag not in VOID:
            self.stack.append(marker)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in SVG_ELEMENTS | VOID:
            self.fail(f"self-closing <{tag}/> not allowed")
        self.check(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID:
            self.fail(f"</{tag}> not allowed")
        if not self.stack:
            self.fail(f"</{tag}> without opening tag")
        top = "p" if self.stack[-1] == "p.lede" else self.stack[-1]
        if top != tag:
            self.fail(f"</{tag}> does not match <{top}>")
        if tag == "svg" and self.need_title:
            self.fail("svg must start with title")
        self.stack.pop()

    def handle_data(self, data: str) -> None:
        if not data.strip():
            return
        if not self.stack:
            self.fail("text outside an element")
        if self.stack[-1] == "h1":
            self.title += data
        elif self.stack[-1] == "p.lede":
            self.lede += data

    def handle_comment(self, data: str) -> None:
        self.fail("comments not allowed")

    def handle_decl(self, decl: str) -> None:
        self.fail("declarations not allowed")

    def unknown_decl(self, data: str) -> None:
        self.fail("declarations not allowed")

    def handle_pi(self, data: str) -> None:
        self.fail("processing instructions not allowed")

    def close(self) -> None:
        super().close()
        if self.stack:
            self.fail(f"<{self.stack[-1]}> never closed")
        if self.top_level < 2 or not self.title.strip() or not self.lede.strip():
            self.fail("missing h1 or lede")


def read_post(path: Path) -> Post:
    stem = path.stem
    if len(stem) < 10 or not stem[:8].isdigit() or stem[8] != "-":
        raise SystemExit(f"posts/{path.name}: name must be YYYYMMDD-<slug>.html")
    try:
        date = datetime.datetime.strptime(stem[:8], "%Y%m%d").date()
    except ValueError:
        raise SystemExit(f"posts/{path.name}: bad date {stem[:8]}") from None
    slug = stem[9:]
    if not SLUG.fullmatch(slug) or slug == "posts":
        raise SystemExit(f"posts/{path.name}: bad slug {slug}")
    text = path.read_text(encoding="utf-8")
    linter = Linter(path)
    linter.feed(text)
    linter.close()
    return Post(date, slug, " ".join(linter.title.split()), " ".join(linter.lede.split()), text)


def nice(date: datetime.date) -> str:
    return f"{date.day} {date:%B %Y}"


def page(title: str, description: str, canonical: str, root: str, css: str, og_type: str, crumbs: str, content: str) -> str:
    t, d, c = (escape(value, quote=True) for value in (title, description, canonical))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t}</title>
<meta name="description" content="{d}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{c}">
<meta property="og:site_name" content="PrizeAtlas">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:url" content="{c}">
<meta name="twitter:card" content="summary">
<link rel="icon" href="{root}favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{root}static/style.css">
<link rel="stylesheet" href="{css}">
</head>
<body>
<header class="site-header"><a class="site-name" href="{root}">PrizeAtlas</a></header>
<nav class="breadcrumbs" aria-label="Breadcrumb"><ol>{crumbs}</ol></nav>
<main>
{content}
</main>
<footer><p><a href="{root}about/">About</a> · <a href="{root}awards.csv" download>Download CSV</a></p></footer>
</body>
</html>
"""


def render_post(post: Post) -> str:
    body = post.body.replace('href="/', 'href="../../').replace("href='/", "href='../../")
    crumbs = f'<li><a href="../../">Home</a></li><li><a href="../">Blog</a></li><li><span aria-current="page">{escape(post.title)}</span></li>'
    content = (
        f'<article class="post">\n<p class="date"><time datetime="{post.date.isoformat()}">{nice(post.date)}</time></p>\n{body.strip()}\n</article>\n'
        f'<p class="more"><a href="../">← All posts</a></p>'
    )
    return page(f"{post.title} | PrizeAtlas Blog", post.lede, f"{BASE_URL}{post.slug}/", "../../", "../blog.css", "article", crumbs, content)


def render_index(posts: list[Post]) -> str:
    items = "\n".join(
        f'<li><time datetime="{p.date.isoformat()}">{nice(p.date)}</time> <a href="{p.slug}/">{escape(p.title)}</a><p>{escape(p.lede)}</p></li>'
        for p in sorted(posts, key=lambda p: (p.date, p.slug), reverse=True)
    )
    crumbs = '<li><a href="../">Home</a></li><li><span aria-current="page">Blog</span></li>'
    content = f'<h1>Blog</h1>\n<ul class="posts">\n{items}\n</ul>'
    description = "Articles on the world's major science prizes and their laureates."
    return page("Blog | PrizeAtlas", description, BASE_URL, "../", "blog.css", "website", crumbs, content)


def main() -> None:
    paths = sorted(POSTS_DIR.glob("*.html"))
    if not paths:
        raise SystemExit("posts/: no posts")
    posts = [read_post(path) for path in paths]
    seen: set[str] = set()
    for path, post in zip(paths, posts):
        if post.slug in seen:
            raise SystemExit(f"posts/{path.name}: duplicate slug {post.slug}")
        seen.add(post.slug)

    pages = {BLOG_DIR / post.slug / "index.html": render_post(post) for post in posts}
    for path, post in zip(paths, posts):
        size = len(pages[BLOG_DIR / post.slug / "index.html"].encode("utf-8"))
        if size > MAX_BYTES:
            raise SystemExit(f"posts/{path.name}: page is {size} bytes, limit {MAX_BYTES}")
    pages[BLOG_DIR / "index.html"] = render_index(posts)

    for path, html in pages.items():
        path.parent.mkdir(exist_ok=True)
        path.write_text(html, encoding="utf-8")
        print(f"wrote {path} bytes={len(html.encode('utf-8'))}")


if __name__ == "__main__":
    main()
