from __future__ import annotations

import re
import shutil
import sqlite3
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from website import build


class WebsiteBuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.website = self.directory / "website"
        shutil.copytree(Path(build.__file__).parent / "templates", self.website / "templates")
        shutil.copytree(Path(build.__file__).parent / "static", self.website / "static")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def create_database(
        self,
        rankings: list[tuple[str, str, str, str, int]],
        records: list[dict[str, str]],
    ) -> Path:
        database = self.directory / "awards.sqlite3"
        columns = ", ".join(f'"{column}" TEXT' for column in build.AWARD_COLUMNS)
        placeholders = ", ".join("?" for _ in build.AWARD_COLUMNS)
        with sqlite3.connect(database) as connection:
            connection.execute(f"CREATE TABLE awards ({columns}) STRICT")
            connection.execute(
                """
                CREATE TABLE award_ranking (
                    award_wikidata_qid TEXT PRIMARY KEY,
                    prize_name TEXT NOT NULL UNIQUE,
                    slug TEXT NOT NULL,
                    url TEXT NOT NULL,
                    score INTEGER NOT NULL UNIQUE,
                    blurb TEXT NOT NULL,
                    reasoning TEXT NOT NULL
                ) STRICT
                """
            )
            connection.executemany(
                "INSERT INTO award_ranking VALUES (?, ?, ?, ?, ?, 'Blurb.', 'Reasoning.')",
                rankings,
            )
            connection.executemany(
                f"INSERT INTO awards VALUES ({placeholders})",
                [tuple(record.get(column, "") for column in build.AWARD_COLUMNS) for record in records],
            )
        return database

    def test_slug_and_base_url_contract(self) -> None:
        self.assertEqual("physics", build.slugify("Physics"))
        self.assertEqual("1983-1984", build.slugify("1983/1984"))
        self.assertEqual("ngo-bao-chau", build.slugify("Ngô Bao Châu"))
        self.assertEqual("sren", build.slugify("Søren"))
        self.assertEqual("frank-h-shu", build.slugify("Frank H. Shu (徐遐生)"))
        self.assertEqual(
            "https://en.wikipedia.org/w/index.php?search=Ng%C3%B4+B%E1%BA%A3o+Ch%C3%A2u",
            build.wikipedia_search_url("Ngô Bảo Châu"),
        )
        self.assertEqual("https://example.org/awards/", build.normalize_base_url("https://example.org/awards"))
        for value in (
            "http://example.org/",
            "https:///awards/",
            "https://user@example.org/",
            "https://example.org/?query=yes",
            "https://example.org/#fragment",
        ):
            with self.subTest(value=value), self.assertRaises(build.BuildFailure):
                build.normalize_base_url(value)

    def test_complete_build_routes_metadata_escaping_and_relative_links(self) -> None:
        rankings = [
            ("Q1", "Nobel Prize", "nobel-prize", "https://example.org/nobel", 100),
            ("Q2", "Turing Award", "turing-award", "https://example.org/turing", 90),
            ("Q3", "Japan Prize", "japan-prize", "https://example.org/japan", 80),
        ]
        records = [
            {
                "award_record_id": "nobel-1",
                "award_wikidata_qid": "Q1",
                "prize_name": "Nobel Prize",
                "prize": "The Nobel Prize in Physics 1939",
                "category": "Physics",
                "year": "1939",
                "full_name": "Ernest Orlando Lawrence",
                "laureate_type": "Individual",
                "motivation": "<em>unsafe</em>",
            },
            {
                "award_record_id": "nobel-2",
                "award_wikidata_qid": "Q1",
                "prize_name": "Nobel Prize",
                "prize": "The Nobel Prize in Chemistry 1940",
                "category": "Chemistry",
                "year": "1940",
                "full_name": "Example Chemist",
            },
            {
                "award_record_id": "turing-1",
                "award_wikidata_qid": "Q2",
                "prize_name": "Turing Award",
                "prize": "Turing Award",
                "category": "Computer science",
                "year": "1989",
                "full_name": "Organization Example",
                "laureate_type": "Organization",
            },
            {
                "award_record_id": "japan-1",
                "award_wikidata_qid": "Q3",
                "prize_name": "Japan Prize",
                "prize": "Japan Prize",
                "category": "Electronics, Information and Communication",
                "year": "2000",
                "full_name": "First Recipient",
            },
            {
                "award_record_id": "japan-2",
                "award_wikidata_qid": "Q3",
                "prize_name": "Japan Prize",
                "prize": "Japan Prize",
                "category": "Electronics / Information and Communication",
                "year": "2001",
                "full_name": "Second Recipient",
            },
        ]
        database = self.create_database(rankings, records)

        plan = build.build_site(database, "https://example.org/awards/", self.website)

        self.assertEqual((3, 4, 5), (plan.prize_count, plan.category_count, plan.winner_count))
        physics = self.website / "dist/nobel-prize/physics/1939/ernest-orlando-lawrence/index.html"
        physics_category = self.website / "dist/nobel-prize/physics/index.html"
        turing = self.website / "dist/turing-award/1989/organization-example/index.html"
        self.assertTrue(physics.is_file())
        self.assertTrue(turing.is_file())
        self.assertTrue(
            (
                self.website
                / "dist/japan-prize/electronics-information-and-communication-2/2000/first-recipient/index.html"
            ).is_file()
        )

        physics_html = physics.read_text()
        self.assertIn("<title>Nobel Prize for Physics 1939 — Ernest Orlando Lawrence</title>", physics_html)
        self.assertIn('href="../../../../favicon.svg"', physics_html)
        self.assertIn('href="../../../../static/style.css"', physics_html)
        self.assertIn("&lt;em&gt;unsafe&lt;/em&gt;", physics_html)
        self.assertNotIn("<em>unsafe</em>", physics_html)
        self.assertIn('href="../"', physics_html)
        self.assertIn(
            'href="https://en.wikipedia.org/w/index.php?search=Ernest+Orlando+Lawrence"',
            physics_html,
        )
        physics_category_html = physics_category.read_text()
        self.assertIn('href="1939/ernest-orlando-lawrence/">Ernest Orlando Lawrence</a>', physics_category_html)
        self.assertIn("&lt;em&gt;unsafe&lt;/em&gt;", physics_category_html)
        home_html = (self.website / "dist/index.html").read_text()
        self.assertIn(
            'href="https://example.org/nobel" aria-label="Nobel Prize official website"',
            home_html,
        )
        turing_html = turing.read_text()
        self.assertIn("<title>Turing Award for Computer science 1989 — Organization Example</title>", turing_html)
        self.assertIn("<dt>Type</dt><dd>Organization</dd>", turing_html)
        self.assertNotIn("/computer-science/", turing_html)

        root = ElementTree.parse(self.website / "dist/sitemap.xml").getroot()
        locations = [element.text for element in root.findall(".//{*}loc")]
        self.assertEqual(len(plan.jobs), len(locations))
        self.assertIn(
            "https://example.org/awards/nobel-prize/physics/1939/ernest-orlando-lawrence/",
            locations,
        )
        for path in (self.website / "dist", *(self.website / "dist").rglob("*")):
            mode = stat.S_IMODE(path.stat().st_mode)
            self.assertEqual(0o2755 if path.is_dir() else 0o644, mode, path)

        dist = self.website / "dist"
        generated = {path.resolve() for path in dist.rglob("*") if path.is_file()}
        for html_path in dist.rglob("*.html"):
            document = html_path.read_text()
            for href in re.findall(r'href="([^"]+)"', document):
                if urlsplit(href).scheme:
                    continue
                if href.startswith("/"):
                    # Only the error page links absolutely; its links carry the deployment path prefix.
                    self.assertTrue(href.startswith("/awards/"), f"{html_path}: {href}")
                    resolved = (dist / href[len("/awards/") :]).resolve()
                else:
                    resolved = (html_path.parent / href).resolve()
                target = resolved / "index.html" if href.endswith("/") else resolved
                self.assertIn(target, generated, f"{html_path}: {href}")

    def test_error_page_and_robots_serve_from_the_deployment_root(self) -> None:
        rankings = [("Q1", "Test Prize", "test-prize", "https://example.org/prize", 100)]
        records = [
            {
                "award_record_id": "record-1",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "2000",
                "full_name": "Example Winner",
            }
        ]
        database = self.create_database(rankings, records)

        plan = build.build_site(database, "https://example.org/awards/", self.website)

        robots = (self.website / "dist/robots.txt").read_text()
        self.assertIn("Sitemap: https://example.org/awards/sitemap.xml", robots)

        error_html = (self.website / "dist/404.html").read_text()
        self.assertIn("<title>Page not found</title>", error_html)
        self.assertIn('<meta name="robots" content="noindex">', error_html)
        self.assertIn('href="/awards/static/style.css"', error_html)
        self.assertIn('href="/awards/favicon.svg"', error_html)
        self.assertIn('href="/awards/"', error_html)
        self.assertNotIn("<link rel=\"canonical\"", error_html)

        # The error page is not a route: it must stay out of the sitemap and the page counts.
        root = ElementTree.parse(self.website / "dist/sitemap.xml").getroot()
        locations = [element.text for element in root.findall(".//{*}loc")]
        self.assertEqual(len(plan.jobs), len(locations))
        self.assertNotIn("https://example.org/awards/404.html", locations)

    def test_latest_thirty_prefixes_and_same_prefix_labels(self) -> None:
        rankings = [("Q1", "Test Prize", "test-prize", "https://example.org/prize", 100)]
        records = []
        for offset in range(31):
            year = str(2000 - offset)
            records.append(
                {
                    "award_record_id": f"record-{offset:02d}",
                    "award_wikidata_qid": "Q1",
                    "prize_name": "Test Prize",
                    "year": year,
                    "full_name": f"Winner {offset}",
                }
            )
        records.append(
            {
                "award_record_id": "record-special",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "1971 (special)",
                "full_name": "Special Winner",
            }
        )
        database = self.create_database(rankings, records)

        build.build_site(database, "https://example.org/", self.website)

        html = (self.website / "dist/test-prize/index.html").read_text()
        disclosure = html.index("<details>")
        self.assertLess(html.index("Winner 29"), disclosure)
        self.assertGreater(html.index("Winner 30"), disclosure)
        self.assertLess(html.index("Special Winner"), disclosure)

    def test_scoped_collisions_preserve_previous_output(self) -> None:
        rankings = [("Q1", "Test Prize", "test-prize", "https://example.org/prize", 100)]
        cases = (
            [
                {
                    "award_record_id": "one",
                    "award_wikidata_qid": "Q1",
                    "prize_name": "Test Prize",
                    "year": "1983/1984",
                    "full_name": "One",
                },
                {
                    "award_record_id": "two",
                    "award_wikidata_qid": "Q1",
                    "prize_name": "Test Prize",
                    "year": "1983-1984",
                    "full_name": "Two",
                },
            ],
            [
                {
                    "award_record_id": "one",
                    "award_wikidata_qid": "Q1",
                    "prize_name": "Test Prize",
                    "year": "1983",
                    "full_name": "Same Winner",
                },
                {
                    "award_record_id": "two",
                    "award_wikidata_qid": "Q1",
                    "prize_name": "Test Prize",
                    "year": "1983",
                    "full_name": "Same-Winner",
                },
            ],
        )
        for number, records in enumerate(cases):
            with self.subTest(number=number):
                database = self.create_database(rankings, records)
                dist = self.website / "dist"
                dist.mkdir(exist_ok=True)
                marker = dist / "marker"
                marker.write_bytes(b"previous")
                with self.assertRaises(build.BuildFailure):
                    build.build_site(database, "https://example.org/", self.website)
                self.assertEqual(b"previous", marker.read_bytes())
                database.unlink()

    def test_sitemap_splits_at_url_limit(self) -> None:
        output = self.directory / "sitemaps"
        output.mkdir()
        routes = [f"/route-{number}/" for number in range(50_001)]

        self.assertEqual(50_001, build.write_sitemaps(output, routes, "https://example.org/base/"))

        index = ElementTree.parse(output / "sitemap.xml").getroot()
        sitemap_locations = [element.text for element in index.findall(".//{*}loc")]
        self.assertEqual(
            [
                "https://example.org/base/sitemap-0001.xml",
                "https://example.org/base/sitemap-0002.xml",
            ],
            sitemap_locations,
        )
        page_locations = []
        for sitemap in sorted(output.glob("sitemap-*.xml")):
            page_locations.extend(element.text for element in ElementTree.parse(sitemap).getroot().findall(".//{*}loc"))
        self.assertEqual(50_001, len(page_locations))
        self.assertEqual(len(page_locations), len(set(page_locations)))

    def test_worker_failure_preserves_output_and_uses_eight_workers(self) -> None:
        rankings = [("Q1", "Test Prize", "test-prize", "https://example.org/prize", 100)]
        records = [
            {
                "award_record_id": "one",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "2000",
                "full_name": "Winner",
            }
        ]
        database = self.create_database(rankings, records)
        dist = self.website / "dist"
        dist.mkdir()
        marker = dist / "marker"
        marker.write_bytes(b"previous")
        real_executor = build.ThreadPoolExecutor
        workers: list[int] = []

        def executor(*args: object, **kwargs: object) -> object:
            workers.append(kwargs["max_workers"])
            return real_executor(*args, **kwargs)

        with (
            mock.patch.object(build, "ThreadPoolExecutor", side_effect=executor),
            mock.patch.object(build, "_render_job", side_effect=RuntimeError("render failed")),
            self.assertRaises(RuntimeError),
        ):
            build.build_site(database, "https://example.org/", self.website)

        self.assertEqual([8], workers)
        self.assertEqual(b"previous", marker.read_bytes())

    def test_promotion_failure_rolls_back_previous_output(self) -> None:
        staging = self.website / ".dist-staging-test"
        dist = self.website / "dist"
        staging.mkdir()
        dist.mkdir()
        (staging / "new").write_bytes(b"new")
        (dist / "old").write_bytes(b"old")
        real_rename = Path.rename

        def rename(path: Path, target: Path) -> Path:
            if path == staging:
                raise OSError("forced promotion failure")
            return real_rename(path, target)

        with mock.patch.object(Path, "rename", autospec=True, side_effect=rename), self.assertRaises(OSError):
            build._promote(staging, dist)

        self.assertEqual(b"old", (dist / "old").read_bytes())
        self.assertTrue(staging.is_dir())

    def test_backup_cleanup_failure_keeps_new_output_active(self) -> None:
        staging = self.website / ".dist-staging-test"
        dist = self.website / "dist"
        staging.mkdir()
        dist.mkdir()
        (staging / "new").write_bytes(b"new")
        (dist / "old").write_bytes(b"old")
        errors = StringIO()

        with mock.patch.object(build.shutil, "rmtree", side_effect=OSError("forced cleanup failure")), redirect_stderr(errors):
            build._promote(staging, dist)

        self.assertEqual(b"new", (dist / "new").read_bytes())
        backups = list(self.website.glob(".dist-backup-*"))
        self.assertEqual(1, len(backups))
        self.assertEqual(b"old", (backups[0] / "old").read_bytes())
        self.assertIn("operation=backup-cleanup", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
