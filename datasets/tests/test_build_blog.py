# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import build_blog

VALID = """<h1>Fixture title</h1>
<p class="lede">Fixture lede &amp; more.</p>
<h2>Part</h2>
<p>See <a href="/nobel-prize/">Nobel</a> and <a href="https://example.org/">source</a>.<br></p>
<figure><svg viewBox="0 0 320 40" role="img"><title>Bars</title><rect x="0" y="0" width="10" height="10" fill="currentColor"/></svg>
<figcaption>One bar.</figcaption></figure>
"""


class BlogBuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.blog = Path(self.temporary.name) / "blog"
        self.posts = self.blog / "posts"
        self.posts.mkdir(parents=True)
        for name, value in (("BLOG_DIR", self.blog), ("POSTS_DIR", self.posts)):
            patcher = mock.patch.object(build_blog, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def post(self, body: str, name: str = "20261108-fixture.html") -> None:
        (self.posts / name).write_text(body, encoding="utf-8")

    def build(self) -> None:
        with mock.patch("builtins.print"):
            build_blog.main()

    def assertFails(self, body: str, message: str, name: str = "20261108-fixture.html") -> None:
        self.post(body, name)
        with self.assertRaises(SystemExit) as caught:
            self.build()
        self.assertIn(message, str(caught.exception))
        self.assertEqual([], [path for path in self.blog.iterdir() if path.name != "posts"])

    def test_valid_post_renders_page_and_index(self) -> None:
        self.post(VALID)
        self.build()
        page = (self.blog / "fixture/index.html").read_text()
        self.assertIn('href="../../nobel-prize/"', page)
        self.assertIn('href="https://example.org/"', page)
        self.assertIn('<link rel="canonical" href="https://prizeatlas.org/blog/fixture/">', page)
        self.assertIn("<title>Fixture title | PrizeAtlas Blog</title>", page)
        self.assertIn('<meta name="description" content="Fixture lede &amp; more.">', page)
        self.assertIn('<time datetime="2026-11-08">8 November 2026</time>', page)
        self.assertIn('href="../../static/style.css"', page)
        index = (self.blog / "index.html").read_text()
        self.assertIn('<a href="fixture/">Fixture title</a>', index)

    def test_index_lists_newest_first(self) -> None:
        self.post(VALID, "20260101-older.html")
        self.post(VALID.replace("Fixture title", "Newer title"), "20261201-newer.html")
        self.build()
        index = (self.blog / "index.html").read_text()
        self.assertLess(index.index("Newer title"), index.index("Fixture title"))

    def test_second_run_is_identical(self) -> None:
        self.post(VALID)
        self.build()
        first = (self.blog / "fixture/index.html").read_text()
        self.build()
        self.assertEqual(first, (self.blog / "fixture/index.html").read_text())

    def test_name_rules(self) -> None:
        self.assertFails(VALID, "bad date 20261340", "20261340-x.html")

    def test_reserved_slug(self) -> None:
        self.assertFails(VALID, "bad slug posts", "20261108-posts.html")

    def test_text_outside_an_element(self) -> None:
        self.assertFails("stray\n" + VALID, "text outside an element")

    def test_missing_lede(self) -> None:
        self.assertFails("<h1>Title</h1>\n<p>Body.</p>\n", 'h1 must be followed by p class="lede"')

    def test_link_inside_h1(self) -> None:
        self.assertFails(VALID.replace("<h1>Fixture title</h1>", '<h1><a href="/x/">Fixture</a></h1>'), "h1 and lede are text only")

    def test_script_not_allowed(self) -> None:
        self.assertFails(VALID + "<script>alert(1)</script>\n", "element script not allowed")

    def test_div_not_allowed(self) -> None:
        self.assertFails(VALID + "<div>x</div>\n", "element div not allowed")

    def test_style_attribute_not_allowed(self) -> None:
        self.assertFails(VALID.replace("<h2>Part</h2>", '<h2 style="color:red">Part</h2>'), "attribute style not allowed on h2")

    def test_fill_must_be_current_color(self) -> None:
        self.assertFails(VALID.replace('fill="currentColor"', 'fill="#f00"'), "fill must be currentColor or none")

    def test_svg_must_start_with_title(self) -> None:
        self.assertFails(VALID.replace("<title>Bars</title>", ""), "svg must start with title")

    def test_http_link_not_allowed(self) -> None:
        self.assertFails(VALID.replace('href="https://example.org/"', 'href="http://example.org/"'), "href must start with / or https://")

    def test_unclosed_element(self) -> None:
        self.assertFails(VALID + "<p><strong>open</p>\n", "</p> does not match <strong>")

    def test_never_closed(self) -> None:
        self.assertFails(VALID + "<p>open\n", "<p> never closed")

    def test_self_closing_html_not_allowed(self) -> None:
        self.assertFails(VALID + "<p/>\n", "self-closing <p/> not allowed")

    def test_comment_not_allowed(self) -> None:
        self.assertFails(VALID + "<!-- draft -->\n", "comments not allowed")

    def test_empty_posts(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            self.build()
        self.assertIn("no posts", str(caught.exception))

    def test_page_over_budget(self) -> None:
        self.assertFails(VALID + "<p>" + "x" * build_blog.MAX_BYTES + "</p>\n", "limit 61440")

    def test_duplicate_slug(self) -> None:
        self.post(VALID, "20260101-fixture.html")
        self.assertFails(VALID, "duplicate slug fixture", "20261108-fixture.html")


if __name__ == "__main__":
    unittest.main()
