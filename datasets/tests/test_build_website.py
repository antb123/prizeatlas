from __future__ import annotations

import json
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
        self.assertIn("<title>Ernest Orlando Lawrence — Nobel Prize for Physics, 1939</title>", physics_html)
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
        self.assertIn("<title>Organization Example — Turing Award for Computer science, 1989</title>", turing_html)
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

    def test_metadata_is_unique_and_structured_data_is_safe(self) -> None:
        rankings = [("Q1", "Nobel Prize", "nobel-prize", "https://example.org/nobel", 100)]
        records = [
            {
                "award_record_id": "nobel-1",
                "award_wikidata_qid": "Q1",
                "prize_name": "Nobel Prize",
                "category": "Physics",
                "year": "2024",
                "full_name": "Geoffrey Hinton",
                "laureate_wikidata_qid": "Q92894",
                "laureate_type": "Individual",
                "birth_date": "1947-12-06",
                "birth_city": "London",
                "birth_country": "United Kingdom",
                "affiliation_name": "University of Toronto",
                # A citation that would close the JSON-LD block early if it were not escaped.
                "motivation": "for work on </script><script>alert(1)</script> networks",
            },
            {
                "award_record_id": "nobel-2",
                "award_wikidata_qid": "Q1",
                "prize_name": "Nobel Prize",
                "category": "Chemistry",
                "year": "2024",
                "full_name": "Second Laureate",
                "laureate_wikidata_qid": "Q2",
            },
        ]
        database = self.create_database(rankings, records)

        build.build_site(database, "https://example.org/", self.website)

        winner = (self.website / "dist/nobel-prize/physics/2024/geoffrey-hinton/index.html").read_text()
        self.assertIn('<meta property="og:title" content="Geoffrey Hinton — Nobel Prize for Physics, 2024">', winner)
        self.assertIn('<meta name="twitter:card" content="summary">', winner)
        self.assertIn('<meta property="og:url" content="https://example.org/nobel-prize/physics/2024/geoffrey-hinton/">', winner)
        self.assertIn("At the time: University of Toronto.", winner)

        block = winner.split('<script type="application/ld+json">')[1].split("</script>")[0]
        payload = json.loads(block)
        graph = {entry["@type"]: entry for entry in payload["@graph"]}
        self.assertEqual("Geoffrey Hinton", graph["Person"]["name"])
        self.assertEqual("https://www.wikidata.org/wiki/Q92894", graph["Person"]["sameAs"])
        self.assertEqual("1947-12-06", graph["Person"]["birthDate"])
        self.assertEqual("London, United Kingdom", graph["Person"]["birthPlace"]["name"])
        self.assertEqual("Nobel Prize for Physics, 2024", graph["Person"]["award"])
        self.assertEqual(5, len(graph["BreadcrumbList"]["itemListElement"]))
        # Citations never enter the schema, so the injected tag cannot reach the block at all.
        self.assertNotIn("alert(1)", block)

        # A field that does reach the schema is escaped, so "</script>" cannot close the block early.
        hostile = build.AwardRecord(
            *(
                {"full_name": "Test", "affiliation_name": "</script><script>alert(1)</script>"}.get(column, "")
                for column in build.AWARD_COLUMNS
            )
        )
        rendered = build._structured_data(
            "https://example.org/",
            build.PageJob("winner.html", "/x/", "t", "d", (), {"schema": build._laureate_schema(hostile, "https://example.org/x/")}),
        )
        self.assertNotIn("<script>", rendered)
        self.assertIn("\\u003c/script>", rendered)
        self.assertEqual("</script><script>alert(1)</script>", json.loads(rendered)["@graph"][0]["affiliation"]["name"])

        # The homepage has no breadcrumbs and no laureate, so it emits no structured data at all.
        self.assertNotIn("application/ld+json", (self.website / "dist/index.html").read_text())

        descriptions = [
            re.search(r'name="description" content="([^"]*)"', path.read_text()).group(1)
            for path in (self.website / "dist").rglob("*.html")
        ]
        self.assertEqual(len(descriptions), len(set(descriptions)), "every page needs its own description")

    def test_shared_citation_prints_once_and_year_pages_link_neighbours(self) -> None:
        rankings = [("Q1", "Nobel Prize", "nobel-prize", "https://example.org/nobel", 100)]
        shared = "for foundational discoveries in machine learning"
        records = [
            {
                "award_record_id": "nobel-1",
                "award_wikidata_qid": "Q1",
                "prize_name": "Nobel Prize",
                "category": "Physics",
                "year": "2024",
                "full_name": "John J. Hopfield",
                "motivation": shared,
            },
            {
                "award_record_id": "nobel-2",
                "award_wikidata_qid": "Q1",
                "prize_name": "Nobel Prize",
                "category": "Physics",
                "year": "2024",
                "full_name": "Geoffrey Hinton",
                "motivation": shared,
            },
            {
                "award_record_id": "nobel-3",
                "award_wikidata_qid": "Q1",
                "prize_name": "Nobel Prize",
                "category": "Physics",
                "year": "2023",
                "full_name": "Solo Laureate",
                "motivation": "for something else entirely",
            },
            {
                "award_record_id": "nobel-4",
                "award_wikidata_qid": "Q1",
                "prize_name": "Nobel Prize",
                "category": "Chemistry",
                "year": "2024",
                "full_name": "Other Category",
            },
        ]
        database = self.create_database(rankings, records)

        build.build_site(database, "https://example.org/", self.website)

        # Two laureates share one citation, so it appears once on both the category and the year page.
        category_html = (self.website / "dist/nobel-prize/physics/index.html").read_text()
        self.assertEqual(1, category_html.count(shared))
        self.assertIn("John J. Hopfield", category_html)
        self.assertIn("Geoffrey Hinton", category_html)

        year_html = (self.website / "dist/nobel-prize/physics/2024/index.html").read_text()
        self.assertEqual(1, year_html.count(shared))
        # 2024 is the latest Physics year, so it links back to 2023 and offers no next link.
        self.assertIn('href="../2023/"', year_html)
        self.assertNotIn('rel="next"', year_html)
        self.assertIn('rel="next"', (self.website / "dist/nobel-prize/physics/2023/index.html").read_text())
        # Chemistry has a single year, so its year page has no neighbours at all.
        self.assertNotIn("<nav class=\"pagination\"", (self.website / "dist/nobel-prize/chemistry/2024/index.html").read_text())

        hinton = (self.website / "dist/nobel-prize/physics/2024/geoffrey-hinton/index.html").read_text()
        self.assertIn("Shared with", hinton)
        self.assertIn('href="../john-j-hopfield/"', hinton)
        # A sole recipient has nobody to share with.
        self.assertNotIn("Shared with", (self.website / "dist/nobel-prize/physics/2023/solo-laureate/index.html").read_text())

    def test_person_pages_merge_awards_by_laureate_qid(self) -> None:
        rankings = [
            ("Q1", "Nobel Prize", "nobel-prize", "https://example.org/nobel", 100),
            ("Q2", "Wolf Prize", "wolf-prize", "https://example.org/wolf", 90),
        ]
        records = [
            {
                "award_record_id": "wolf-1",
                "award_wikidata_qid": "Q2",
                "prize_name": "Wolf Prize",
                "category": "Medicine",
                "year": "2011",
                "full_name": "Shinya Yamanaka",
                "laureate_wikidata_qid": "Q188345",
            },
            {
                "award_record_id": "nobel-1",
                "award_wikidata_qid": "Q1",
                "prize_name": "Nobel Prize",
                "category": "Medicine",
                "year": "2012",
                "full_name": "Shinya Yamanaka",
                "laureate_wikidata_qid": "Q188345",
            },
            {
                "award_record_id": "nobel-2",
                "award_wikidata_qid": "Q1",
                "prize_name": "Nobel Prize",
                "category": "Physics",
                "year": "2012",
                "full_name": "Unlinked Laureate",
            },
        ]
        database = self.create_database(rankings, records)

        plan = build.build_site(database, "https://example.org/", self.website)

        self.assertEqual(1, plan.person_count)
        person = self.website / "dist/people/shinya-yamanaka/index.html"
        person_html = person.read_text()
        # Awards ascend by year, so a career reads in the order it happened.
        self.assertLess(person_html.index("Wolf Prize"), person_html.index("Nobel Prize"))
        # Wolf Prize has a single category here, so it is not category-routed; Nobel has two and is.
        self.assertIn('href="../../wolf-prize/2011/shinya-yamanaka/"', person_html)
        self.assertIn('href="../../nobel-prize/medicine/2012/shinya-yamanaka/"', person_html)

        linked = (self.website / "dist/nobel-prize/medicine/2012/shinya-yamanaka/index.html").read_text()
        self.assertIn("All awards won by Shinya Yamanaka", linked)
        # A record without a laureate QID cannot be merged, so it gets no person page and no link.
        unlinked = (self.website / "dist/nobel-prize/physics/2012/unlinked-laureate/index.html").read_text()
        self.assertNotIn("All awards won by", unlinked)
        self.assertFalse((self.website / "dist/people/unlinked-laureate").exists())

        index_html = (self.website / "dist/people/index.html").read_text()
        self.assertIn('href="shinya-yamanaka/"', index_html)
        # The header People link resolves from every depth.
        self.assertIn('href="people/"', (self.website / "dist/index.html").read_text())
        self.assertIn('href="../people/"', (self.website / "dist/nobel-prize/index.html").read_text())
        self.assertIn('href="../../../../people/"', linked)

    def test_ambiguous_laureate_identity_fails_the_build(self) -> None:
        shared_qid = [
            {
                "award_record_id": "nobel-1",
                "award_wikidata_qid": "Q1",
                "prize_name": "Nobel Prize",
                "year": "1962",
                "full_name": "Francis Harry Compton Crick",
                "laureate_wikidata_qid": "Q123280",
            },
            {
                "award_record_id": "nobel-2",
                "award_wikidata_qid": "Q1",
                "prize_name": "Nobel Prize",
                "year": "1963",
                "full_name": "F.H.C. Crick",
                "laureate_wikidata_qid": "Q123280",
            },
        ]
        with self.assertRaises(build.BuildFailure) as caught:
            build.person_routes([build.AwardRecord(*(record.get(column, "") for column in build.AWARD_COLUMNS)) for record in shared_qid])
        self.assertIn("two names", str(caught.exception))

        colliding = [
            {**shared_qid[0], "laureate_wikidata_qid": "Q1000", "full_name": "Renée Descartes"},
            {**shared_qid[1], "laureate_wikidata_qid": "Q2000", "full_name": "Renee Descartes"},
        ]
        with self.assertRaises(build.BuildFailure) as caught:
            build.person_routes([build.AwardRecord(*(record.get(column, "") for column in build.AWARD_COLUMNS)) for record in colliding])
        self.assertIn("duplicate person slug", str(caught.exception))

    def test_people_index_paginates_and_lists_everyone_once(self) -> None:
        rankings = [("Q1", "Test Prize", "test-prize", "https://example.org/prize", 100)]
        records = [
            {
                "award_record_id": f"record-{number:03d}",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "2000",
                "full_name": f"Laureate Number{number:03d}",
                "laureate_wikidata_qid": f"Q{number}",
            }
            for number in range(1, 251)
        ]
        database = self.create_database(rankings, records)

        with mock.patch.object(build, "PEOPLE_PER_PAGE", 100):
            plan = build.build_site(database, "https://example.org/", self.website)

        self.assertEqual(250, plan.person_count)
        first = (self.website / "dist/people/index.html").read_text()
        third = (self.website / "dist/people/page-3/index.html").read_text()
        self.assertIn('href="page-2/"', first)
        self.assertNotIn("rel=\"prev\"", first)
        self.assertIn('href="../"', third)
        self.assertNotIn("rel=\"next\"", third)

        listed = []
        for page in (self.website / "dist/people/index.html", *sorted((self.website / "dist/people").glob("page-*/index.html"))):
            body = page.read_text().split('class="people-index"')[1].split("</ul>")[0]
            listed.extend(re.findall(r'href="([^"]+)"', body))
        self.assertEqual(250, len(listed))
        self.assertEqual(250, len(set(listed)))

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
        # The prize page carries the most recent 30 award years; older years live on their own year pages.
        self.assertIn("Winner 29", html)
        self.assertIn("Special Winner", html)
        self.assertNotIn("Winner 30", html)
        self.assertIn('href="1970/"', html)
        self.assertTrue((self.website / "dist/test-prize/1970/winner-30/index.html").is_file())

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
