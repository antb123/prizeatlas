from __future__ import annotations

import csv
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

# Both affiliation stores spell the six columns the same way: the flat columns are position 1, the table is 2+.
AFFILIATION_COLUMNS = (
    "affiliation_name",
    "affiliation_sub_name",
    "affiliation_city",
    "affiliation_country",
    "affiliation_coordinates",
    "affiliation_wikidata_qid",
)


def award(extras: tuple[dict[str, str], ...] = (), **values: str) -> build.AwardRecord:
    """One record composed the way `read_database` composes it: the flat values are position 1, `extras` follow."""
    rows = (values, *extras)
    return build.AwardRecord(
        *(values.get(column, "Physics" if column == "high_school_subject" else "") for column in build.AWARD_COLUMNS),
        affiliations=tuple(
            build.AwardAffiliation(position, *(row.get(column, "") for column in AFFILIATION_COLUMNS))
            for position, row in enumerate(rows, start=1)
            if any(row.get(column, "") for column in AFFILIATION_COLUMNS)
        ),
    )


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
        extras: dict[str, list[dict[str, str]]] | None = None,
        profiles: list[tuple[str, str]] | None = None,
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
            connection.execute(
                """
                CREATE TABLE affiliations (
                    affiliation_wikidata_qid TEXT PRIMARY KEY,
                    logo_url TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    application_url TEXT NOT NULL DEFAULT '',
                    kind TEXT NOT NULL DEFAULT ''
                ) STRICT
                """
            )
            connection.execute(
                """
                CREATE TABLE award_extra_affiliations (
                    award_record_id          TEXT    NOT NULL REFERENCES awards(award_record_id),
                    position                 INTEGER NOT NULL CHECK (position >= 2),
                    affiliation_name         TEXT    NOT NULL DEFAULT '',
                    affiliation_sub_name     TEXT    NOT NULL DEFAULT '',
                    affiliation_city         TEXT    NOT NULL DEFAULT '',
                    affiliation_country      TEXT    NOT NULL DEFAULT '',
                    affiliation_coordinates  TEXT    NOT NULL DEFAULT '',
                    affiliation_wikidata_qid TEXT    NOT NULL DEFAULT '',
                    PRIMARY KEY (award_record_id, position)
                ) STRICT
                """
            )
            connection.executemany(
                "INSERT INTO award_ranking VALUES (?, ?, ?, ?, ?, 'Blurb.', 'Reasoning.')",
                rankings,
            )
            connection.executemany(
                f"INSERT INTO awards VALUES ({placeholders})",
                [
                    tuple(record.get(column, "Physics" if column == "high_school_subject" else "") for column in build.AWARD_COLUMNS)
                    for record in records
                ],
            )
            connection.executemany(
                "INSERT INTO award_extra_affiliations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (record_id, position, *(extra.get(column, "") for column in AFFILIATION_COLUMNS))
                    for record_id, rows in (extras or {}).items()
                    for position, extra in enumerate(rows, start=2)
                ],
            )
            connection.executemany(
                "INSERT INTO affiliations (affiliation_wikidata_qid, kind) VALUES (?, ?)",
                profiles or (),
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
        self.assertEqual("http://localhost:8000/", build.normalize_base_url("http://localhost:8000"))
        for value in (
            "http://example.org/",
            "https:///awards/",
            "https://user@example.org/",
            "https://example.org/?query=yes",
            "https://example.org/#fragment",
        ):
            with self.subTest(value=value), self.assertRaises(build.BuildFailure):
                build.normalize_base_url(value)

    def test_explorer_payload_serialization_and_route(self) -> None:
        rankings = [
            build.Ranking("Q1", "First Prize", "first-prize", "https://example.org/first", 100, "Blurb.", "Reasoning."),
            build.Ranking("Q2", "Second Prize", "second-prize", "https://example.org/second", 60, "Blurb.", "Reasoning."),
        ]

        records = [
            award(
                award_record_id="first-1",
                year="2001",
                category="Physics",
                prize_name="First Prize",
                award_wikidata_qid="Q1",
                laureate_wikidata_qid="Q100",
                laureate_type="Individual",
                full_name="Alice Example",
                birth_date="1970-04-03",
                birth_country="Belgium",
                death_country="France",
                affiliation_country="United States",
                citizenship_countries="Belgium; Canada",
                extras=({"affiliation_country": "Belgium"},),
            ),
            award(
                award_record_id="second-1",
                year="1999",
                prize_name="Second Prize",
                award_wikidata_qid="Q2",
                laureate_wikidata_qid="Q100",
                laureate_type="Individual",
                full_name="Alice Example",
                birth_country="Germany",
                death_country="Germany",
                affiliation_country="Canada",
                citizenship_countries="France",
                extras=({"affiliation_country": "Switzerland"},),
            ),
            award(
                award_record_id="second-2",
                year="2002",
                category="Peace",
                prize_name="Second Prize",
                award_wikidata_qid="Q2",
                laureate_type="Organization",
                full_name="Example </script> Institute",
                birth_date="unknown",
                birth_year="unknown",
                affiliation_country="Japan",
            ),
        ]
        population_file = self.directory / "population.json"
        population_file.write_text(
            json.dumps(
                {
                    "population": {
                        "Belgium": 11,
                        "France": 22,
                        "United States": 33,
                        "Canada": 44,
                        "Switzerland": 55,
                        "Japan": 66,
                    }
                }
            )
        )

        payload = build.explorer_payload(rankings, records, {"Q100": "/people/alice-example/"}, population_file)

        self.assertEqual(
            {
                "families": [{"name": "First Prize", "score": 100}, {"name": "Second Prize", "score": 60}],
                "countries": ["Belgium", "France", "United States", "Canada", "Switzerland", "Japan"],
                "subjects": ["Physics"],
                "population": [11, 22, 33, 44, 55, 66],
                "people": [
                    {
                        "n": "Alice Example",
                        "o": 0,
                        "r": "../people/alice-example/",
                        "c": 2,
                        "p": 1.6,
                        "a": [[1999, 1, "", 0], [2001, 0, "Physics", 0]],
                        "bc": 0,
                        "dc": 1,
                        "ac": [0, 2, 3, 4],
                        "cc": [0, 1, 3],
                        "by": 1970,
                    },
                    {
                        "n": "Example </script> Institute",
                        "o": 1,
                        "r": "",
                        "c": 1,
                        "p": 0.6,
                        "a": [[2002, 1, "Peace", 0]],
                        "bc": None,
                        "dc": None,
                        "ac": [5],
                        "cc": [],
                        "by": None,
                    },
                ],
            },
            payload,
        )
        serialized = build.explorer_json(payload)
        self.assertNotIn("<", serialized)
        self.assertEqual("Example </script> Institute", json.loads(serialized)["people"][1]["n"])

        plan = build.create_site_plan(rankings, records, "https://example.org/", "2026-07-26")
        explorer = next(job for job in plan.jobs if job.route == build.EXPLORER_ROUTE)
        self.assertEqual("explorer.html", explorer.template)

    def test_map_coordinates_aggregation_serialization_and_routes(self) -> None:
        self.assertEqual(((-180.0, -90.0), (180.0, 90.0)), build.parse_map_points("-180,-90;180,90", "r1", "affiliation_coordinates", True))
        self.assertEqual(((-73.9, 40.7),), build.parse_map_points("-73.9,40.7", "r1", "birth_coordinates", False))
        for value in ("181,0", "0,91", "nan,0", "1", "1,2,3", "1,2;3,4"):
            with self.subTest(value=value), self.assertRaisesRegex(
                build.BuildFailure,
                "record_id=safe-id field=birth_coordinates",
            ):
                build.parse_map_points(value, "safe-id", "birth_coordinates", False)

        records = [
            award(
                award_record_id="r1",
                year="1999",
                high_school_subject="Math",
                birth_city="Paris",
                birth_country="France",
                birth_coordinates="2.35,48.86",
                affiliation_name="Paris Academy",
                affiliation_city="Paris",
                affiliation_country="France",
                affiliation_coordinates="2.35,48.86",
                extras=(
                    {
                        "affiliation_name": "Boston Institute",
                        "affiliation_city": "Boston",
                        "affiliation_country": "United States",
                        "affiliation_coordinates": "-71.06,42.36",
                    },
                ),
            ),
            award(
                award_record_id="r2",
                year="2001",
                high_school_subject="Physics",
                birth_city="Paris",
                birth_country="France",
                birth_coordinates="2.35,48.86",
                affiliation_name="Paris Institute",
                affiliation_city="Paris",
                affiliation_country="France",
                affiliation_coordinates="2.35,48.86",
            ),
            award(
                award_record_id="r3",
                year="2024",
                high_school_subject="Biology",
                birth_country="Belgium",
                birth_coordinates="4.35,50.85",
            ),
        ]

        payload = build.map_payload(records)
        paris_birth = next(marker for marker in payload["birth"] if marker["title"] == "Paris")
        self.assertEqual(2, paris_birth["count"])
        self.assertEqual({"Math": 1, "Physics": 1}, paris_birth["subjects"])
        self.assertEqual({"1990s": 1, "2000s": 1}, paris_birth["decades"])
        self.assertEqual({"1990s": 1}, paris_birth["subject_decades"]["Math"])
        belgium_birth = next(marker for marker in payload["birth"] if marker["country"] == "Belgium")
        self.assertEqual("", belgium_birth["city"])
        self.assertEqual("Belgium", belgium_birth["title"])

        # Two institutions share the Paris point; r1's second affiliation stands alone in Boston with its own label.
        self.assertEqual(2, len(payload["affiliation"]))
        paris_institution = next(marker for marker in payload["affiliation"] if marker["count"] == 2)
        self.assertEqual("Paris Academy", paris_institution["title"])
        self.assertEqual(1, paris_institution["extra_labels"])
        boston_institution = next(marker for marker in payload["affiliation"] if marker["count"] == 1)
        self.assertEqual("Boston Institute", boston_institution["title"])

        serialized = build.map_json({"birth": [{"title": "</script>"}], "affiliation": []})
        self.assertNotIn("<", serialized)
        self.assertEqual("</script>", json.loads(serialized)["birth"][0]["title"])

        rankings = [build.Ranking("Q1", "Test Prize", "test-prize", "https://example.org/prize", 100, "Blurb.", "Reasoning.")]
        routed_records = [
            award(
                award_record_id="r4",
                award_wikidata_qid="Q1",
                prize_name="Test Prize",
                year="2024",
                high_school_subject="Biology",
                full_name="Example Winner",
                birth_coordinates="4.35,50.85",
            )
        ]
        plan = build.create_site_plan(rankings, routed_records, "https://example.org/", "2026-07-26")
        map_jobs = [job for job in plan.jobs if job.route.startswith(build.MAP_ROUTE)]
        self.assertEqual(1 + len(build.SUBJECTS), len(map_jobs))
        self.assertEqual(len(map_jobs), len({job.route for job in map_jobs}))
        self.assertEqual(len(map_jobs), len({job.title for job in map_jobs}))
        self.assertEqual(len(map_jobs), len({job.description for job in map_jobs}))
        biology = next(job for job in map_jobs if job.route == "/map/biology/")
        self.assertEqual("map.html", biology.template)
        self.assertEqual("Biology", biology.context["initial_subject"])

    def test_nearby_payload_groups_places_and_people(self) -> None:
        records = [
            award(
                award_record_id="r3",
                full_name="Zed < Example",
                laureate_wikidata_qid="Q3",
                birth_city="Shared",
                birth_country="France",
                birth_coordinates="2,48",
                affiliation_name="Common Institute",
                affiliation_city="Paris",
                affiliation_country="France",
                affiliation_coordinates="2,48",
            ),
            award(
                award_record_id="r1",
                full_name="Alice & Example",
                laureate_wikidata_qid="Q1",
                birth_city="Shared",
                birth_country="France",
                birth_coordinates="2,48",
                affiliation_name="Common Institute",
                affiliation_city="Paris",
                affiliation_country="France",
                affiliation_coordinates="2,48",
            ),
            award(
                award_record_id="r2",
                full_name="Alice & Example",
                laureate_wikidata_qid="Q1",
                affiliation_name="Common Institute",
                affiliation_city="Paris",
                affiliation_country="France",
                affiliation_coordinates="2,48",
            ),
            award(
                award_record_id="r4",
                full_name="Bob Example",
                laureate_wikidata_qid="Q2",
                affiliation_name="Other Institute",
                affiliation_city="Paris",
                affiliation_country="France",
                affiliation_coordinates="2,48",
            ),
        ]
        routes = {"Q1": "/people/alice/", "Q2": "/people/bob/", "Q3": "/people/zed/"}
        affiliations = [build.Affiliation("Common Institute", "common-institute", "/affiliations/common-institute/", 2, (), (), (), None)]

        payload = build.nearby_payload(records, routes, affiliations)
        self.assertEqual(
            [["Alice & Example", "../people/alice/"], ["Bob Example", "../people/bob/"], ["Zed < Example", "../people/zed/"]],
            payload["people"],
        )
        self.assertEqual(["a", "b"], [place["k"] for place in payload["places"]])
        institution, birthplace = payload["places"]
        self.assertEqual("Common Institute", institution["n"])
        self.assertEqual(1, institution["x"])
        self.assertEqual("../affiliations/common-institute/", institution["r"])
        self.assertEqual(2, institution["c"])
        self.assertEqual([0, 1, 2], institution["p"])
        self.assertEqual([0, 2], birthplace["p"])
        self.assertEqual(build.map_json(payload), build.map_json(build.nearby_payload(list(reversed(records)), routes, affiliations)))
        self.assertNotIn("<", build.map_json(payload))

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
                "high_school_subject": "Biology",
                "birth_city": "Canton",
                "birth_country": "United States",
                "birth_coordinates": "-81.3784,40.7989",
                "affiliation_coordinates": "-122.2583,37.8719",
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

        # Japan Prize routes by year, so only the Nobel Prize contributes category pages.
        self.assertEqual((3, 2, 5), (plan.prize_count, plan.category_count, plan.winner_count))
        physics = self.website / "dist/nobel-prize/physics/1939/ernest-orlando-lawrence/index.html"
        physics_category = self.website / "dist/nobel-prize/physics/index.html"
        turing = self.website / "dist/turing-award/1989/organization-example/index.html"
        self.assertTrue(physics.is_file())
        self.assertTrue(turing.is_file())
        # The Japan Prize picks its topic afresh each year, so its winners sit under the year, not a category slug.
        self.assertTrue((self.website / "dist/japan-prize/2000/first-recipient/index.html").is_file())
        self.assertFalse((self.website / "dist/japan-prize/electronics-information-and-communication").exists())
        japan_html = (self.website / "dist/japan-prize/index.html").read_text()
        self.assertIn('href="2000/"', japan_html)
        self.assertIn('href="2001/"', japan_html)

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
        self.assertIn('src="static/logos/nobel-prize.png" alt="Nobel Prize logo"', home_html)
        self.assertTrue((self.website / "dist/static/logos/nobel-prize.png").is_file())
        turing_html = turing.read_text()
        self.assertIn("<title>Organization Example — Turing Award for Computer science, 1989</title>", turing_html)
        self.assertIn("<dt>Type</dt><dd>Organization</dd>", turing_html)
        self.assertNotIn("/computer-science/", turing_html)

        map_html = (self.website / "dist/map/index.html").read_text()
        biology_map_html = (self.website / "dist/map/biology/index.html").read_text()
        self.assertIn('<body class="map-layout">', map_html)
        self.assertIn('href="../static/style.css"', map_html)
        self.assertIn('href="./">Map</a>', map_html)
        self.assertIn("leaflet@1.9.4", map_html)
        self.assertIn("sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=", map_html)
        self.assertIn("tile.openstreetmap.org", map_html)
        self.assertIn("OpenStreetMap", map_html)
        self.assertIn("mapped points", map_html)
        self.assertIn("<noscript>", map_html)
        self.assertIn("document.createElement", map_html)
        self.assertIn('element.setAttribute("tabindex", "0")', map_html)
        self.assertIn('event.key !== "Enter" && event.key !== " "', map_html)
        self.assertIn("prefers-reduced-motion: reduce", map_html)
        self.assertIn('const plannedSubject = "Biology";', biology_map_html)
        nearby_html = (self.website / "dist/nearby/index.html").read_text()
        nearby_data = re.search(r'<script id="nearby-data" type="application/json">(.*?)</script>', nearby_html, re.DOTALL)
        self.assertIsNotNone(nearby_data)
        self.assertEqual({"people", "places"}, set(json.loads(nearby_data.group(1))))
        explorer_html = (self.website / "dist/explorer/index.html").read_text()
        self.assertIn('href="../nearby/">Find the winners nearest you</a>', explorer_html)

        root = ElementTree.parse(self.website / "dist/sitemap.xml").getroot()
        locations = [element.text for element in root.findall(".//{*}loc")]
        self.assertEqual(len(plan.jobs), len(locations))
        self.assertIn(
            "https://example.org/awards/nobel-prize/physics/1939/ernest-orlando-lawrence/",
            locations,
        )
        self.assertIn("https://example.org/awards/map/", locations)
        self.assertIn("https://example.org/awards/map/biology/", locations)
        self.assertIn("https://example.org/awards/nearby/", locations)
        for path in (self.website / "dist", *(self.website / "dist").rglob("*")):
            mode = stat.S_IMODE(path.stat().st_mode)
            self.assertEqual(0o2755 if path.is_dir() else 0o644, mode, path)

        dist = self.website / "dist"
        generated = {path.resolve() for path in dist.rglob("*") if path.is_file()}
        for html_path in dist.rglob("*.html"):
            document = html_path.read_text()
            static_html = re.sub(r"<script\b[^>]*>.*?</script>", "", document, flags=re.DOTALL)
            for href in re.findall(r'href="([^"]+)"', static_html):
                if urlsplit(href).scheme or href.startswith("#"):
                    continue
                if href.startswith("/"):
                    # Only the error page links absolutely; its links carry the deployment path prefix.
                    self.assertTrue(href.startswith("/awards/"), f"{html_path}: {href}")
                    resolved = (dist / href[len("/awards/") :]).resolve()
                else:
                    resolved = (html_path.parent / href).resolve()
                target = resolved / "index.html" if href.endswith("/") else resolved
                self.assertIn(target, generated, f"{html_path}: {href}")

    def test_year_routed_prize_names_each_topic_in_the_year(self) -> None:
        rankings = [("Q3", "Japan Prize", "japan-prize", "https://example.org/japan", 80)]
        records = [
            {
                "award_record_id": "japan-1",
                "award_wikidata_qid": "Q3",
                "prize_name": "Japan Prize",
                "category": "Life Sciences",
                "year": "2000",
                "full_name": "Biology Laureate",
                "motivation": "for work in biology",
            },
            {
                "award_record_id": "japan-2",
                "award_wikidata_qid": "Q3",
                "prize_name": "Japan Prize",
                "category": "Materials and Production",
                "year": "2000",
                "full_name": "Materials Laureate",
                "motivation": "for work in materials",
            },
        ]
        database = self.create_database(rankings, records)

        build.build_site(database, "https://example.org/", self.website)

        year_html = (self.website / "dist/japan-prize/2000/index.html").read_text()
        # Two topics share one year, so neither may claim the heading; each recipient group names its own.
        self.assertIn("<title>Japan Prize 2000: Winners</title>", year_html)
        self.assertIn('<p class="group-category">Life Sciences</p>', year_html)
        self.assertIn('<p class="group-category">Materials and Production</p>', year_html)

    def test_correction_links_carry_the_page_and_the_record_id(self) -> None:
        (self.directory / ".env").write_text("# corrections\nCORRECTIONS_EMAIL = 'fixme@example.org'\n", encoding="utf-8")
        rankings = [("Q1", "Nobel Prize", "nobel-prize", "https://example.org/nobel", 100)]
        records = [
            {
                "award_record_id": "nobel-1",
                "award_wikidata_qid": "Q1",
                "prize_name": "Nobel Prize",
                "category": "Physics",
                "year": "2024",
                "full_name": "Geoffrey Hinton",
            },
            {
                "award_record_id": "nobel-2",
                "award_wikidata_qid": "Q1",
                "prize_name": "Nobel Prize",
                "category": "Chemistry",
                "year": "2024",
                "full_name": "Second Laureate",
            },
        ]
        database = self.create_database(rankings, records)

        build.build_site(database, "https://example.org/", self.website)

        winner = (self.website / "dist/nobel-prize/physics/2024/geoffrey-hinton/index.html").read_text()
        self.assertIn("mailto:fixme%40example.org?subject=Correction%3A%20nobel-1", winner)
        self.assertIn("Page%3A%20https%3A//example.org/nobel-prize/physics/2024/geoffrey-hinton/%0ARecord%3A%20nobel-1", winner)
        self.assertIn('<span class="record-id">nobel-1</span>', winner)
        # The footer reports the page it sits on and names no record.
        home = (self.website / "dist/index.html").read_text()
        self.assertIn("mailto:fixme%40example.org?subject=Correction%3A%20https%3A//example.org/", home)
        self.assertNotIn("Record%3A", home)
        # A 404 is served for arbitrary URLs, so it has no page of its own to report.
        self.assertNotIn("mailto:", (self.website / "dist/404.html").read_text())

    def test_correction_links_vanish_without_a_configured_address(self) -> None:
        rankings = [("Q1", "Nobel Prize", "nobel-prize", "https://example.org/nobel", 100)]
        records = [
            {
                "award_record_id": "nobel-1",
                "award_wikidata_qid": "Q1",
                "prize_name": "Nobel Prize",
                "category": "Physics",
                "year": "2024",
                "full_name": "Geoffrey Hinton",
            },
            {
                "award_record_id": "nobel-2",
                "award_wikidata_qid": "Q1",
                "prize_name": "Nobel Prize",
                "category": "Chemistry",
                "year": "2024",
                "full_name": "Second Laureate",
            },
        ]
        database = self.create_database(rankings, records)

        build.build_site(database, "https://example.org/", self.website)

        winner = (self.website / "dist/nobel-prize/physics/2024/geoffrey-hinton/index.html").read_text()
        self.assertNotIn("mailto:", winner)
        self.assertNotIn("Report a correction", winner)

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
        hostile = award(full_name="Test", affiliation_name="</script><script>alert(1)</script>")
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
                "sex": "Male",
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
        self.assertIn("M</p>", person_html)
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
            listed.extend(re.findall(r'<li>\s*<a href="([^"]+)"', body))
        self.assertEqual(250, len(listed))
        self.assertEqual(250, len(set(listed)))

    def test_country_tabs_split_people_and_recorded_institutions(self) -> None:
        rankings = [("Q1", "Test Prize", "test-prize", "https://example.org/prize", 100)]
        records = [
            {
                "award_record_id": "alice-one",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "2000",
                "full_name": "Alice Alpha",
                "laureate_wikidata_qid": "Q100",
                "birth_country": "Belgium",
                "affiliation_name": "University One",
                "affiliation_country": "United States",
            },
            {
                "award_record_id": "alice-two",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "2001",
                "full_name": "Alice Alpha",
                "laureate_wikidata_qid": "Q100",
                "birth_country": "Belgium",
                "affiliation_name": "University One",
                "affiliation_country": "United States",
            },
            {
                "award_record_id": "bob",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "2002",
                "full_name": "Bob Beta",
                "laureate_wikidata_qid": "Q200",
                "birth_country": "Belgium",
                "affiliation_name": "Belgian Academy",
                "affiliation_country": "Belgium",
            },
            {
                "award_record_id": "carol",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "2003",
                "full_name": "Carol Gamma",
                "laureate_wikidata_qid": "Q300",
                "birth_country": "Canada",
                "affiliation_name": "Joint Institute; Partner Lab",
                "affiliation_country": "Canada",
            },
            {
                "award_record_id": "dave",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "2004",
                "full_name": "Dave Delta",
                "laureate_wikidata_qid": "Q400",
                "birth_country": "Canada",
                "affiliation_name": "University One",
                "affiliation_city": "Boston",
                "affiliation_country": "United States",
            },
        ]
        # The second country of a multi-country award is a second affiliation row, not a ";" inside one.
        extras = {
            "alice-one": [{"affiliation_name": "University One", "affiliation_country": "Belgium"}],
            "alice-two": [{"affiliation_name": "University One", "affiliation_country": "Belgium"}],
            "carol": [{"affiliation_name": "Joint Institute; Partner Lab", "affiliation_country": "Switzerland"}],
        }
        database = self.create_database(rankings, records, extras)

        build.build_site(database, "https://example.org/", self.website)

        born_belgium = (self.website / "dist/countries/belgium/index.html").read_text()
        people = (self.website / "dist/countries/index.html").read_text()
        institutions = (self.website / "dist/countries/affiliations/index.html").read_text()
        belgium = (self.website / "dist/countries/affiliations/belgium/index.html").read_text()
        canada = (self.website / "dist/countries/affiliations/canada/index.html").read_text()
        switzerland = (self.website / "dist/countries/affiliations/switzerland/index.html").read_text()
        united_states = (self.website / "dist/countries/affiliations/united-states/index.html").read_text()

        self.assertIn('href="affiliations/">Institutions</a>', people)
        self.assertLess(born_belgium.index("Alice Alpha"), born_belgium.index("Bob Beta"))
        self.assertIn('href="../">Born</a>', institutions)
        self.assertIn('aria-current="page">Institutions</a>', institutions)
        self.assertLess(institutions.index(">Belgium</a>"), institutions.index(">Canada</a>"))
        self.assertIn(">2</span>", institutions)
        self.assertEqual(1, belgium.count(">University One</a>"))
        self.assertIn(">Belgian Academy</a>", belgium)
        self.assertIn(">Joint Institute; Partner Lab</a>", canada)
        self.assertIn(">Joint Institute; Partner Lab</a>", switzerland)
        # The base country route is the people view, so the pre-split URLs still resolve.
        self.assertTrue((self.website / "dist/countries/canada/index.html").is_file())
        self.assertTrue((self.website / "dist/affiliations/university-one/index.html").is_file())
        # Counts are scoped to the country: University One holds two laureates in the US but only one in Belgium.
        self.assertRegex(united_states, r"(?s)>University One</a>.*?rank-count[^>]*>2<")
        self.assertRegex(belgium, r"(?s)>University One</a>.*?rank-count[^>]*>1<")
        # The city recorded for the institution in this country rides on the row.
        self.assertIn("Boston", united_states)
        self.assertRegex(united_states, r"(?s)1 institution ·\s*2 laureates ·\s*1 city")

    def test_second_affiliation_places_one_award_under_both_institutions(self) -> None:
        rankings = [("Q1", "Test Prize", "test-prize", "https://example.org/prize", 100)]
        records = [
            {
                "award_record_id": "shared-one",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "2000",
                "full_name": "Alice Alpha",
                "laureate_wikidata_qid": "Q100",
                "affiliation_name": "Paris Institute",
                "affiliation_city": "Paris",
                "affiliation_country": "France",
            }
        ]
        extras = {"shared-one": [{"affiliation_name": "Boston Institute", "affiliation_city": "Boston", "affiliation_country": "United States"}]}
        database = self.create_database(rankings, records, extras)

        build.build_site(database, "https://example.org/", self.website)

        winner = (self.website / "dist/test-prize/2000/alice-alpha/index.html").read_text()
        # Position orders the affiliations, so the flat row is named before the one from the extras table.
        self.assertIn(">Paris Institute</a>", winner)
        self.assertIn(">Boston Institute</a>", winner)
        self.assertLess(winner.index("Paris Institute"), winner.index("Boston Institute"))

        # One award, two recorded institutions: neither ranking under-counts it.
        paris = (self.website / "dist/affiliations/paris-institute/index.html").read_text()
        boston = (self.website / "dist/affiliations/boston-institute/index.html").read_text()
        self.assertIn('href="../../test-prize/2000/alice-alpha/">Alice Alpha</a>', paris)
        self.assertIn('href="../../test-prize/2000/alice-alpha/">Alice Alpha</a>', boston)

        # Each institution is placed by its own affiliation row, so neither country page borrows the other's city.
        france = (self.website / "dist/countries/affiliations/france/index.html").read_text()
        united_states = (self.website / "dist/countries/affiliations/united-states/index.html").read_text()
        self.assertIn(">Paris Institute</a>", france)
        self.assertIn("Paris", france)
        self.assertNotIn("Boston", france)
        self.assertIn(">Boston Institute</a>", united_states)
        self.assertIn("Boston", united_states)
        self.assertNotIn("Paris", united_states)

    def test_affiliation_ranking_discloses_units_after_the_first_three(self) -> None:
        rankings = [("Q1", "Test Prize", "test-prize", "https://example.org/prize", 100)]
        records = [
            {
                "award_record_id": f"one-{index}",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "2000",
                "full_name": f"One Person {index}",
                "laureate_wikidata_qid": f"Q10{index}",
                "affiliation_name": "University One",
                "affiliation_sub_name": f"Unit {letter}",
            }
            for index, letter in enumerate("ABCDE", start=1)
        ]
        records.extend(
            {
                "award_record_id": f"three-{index}",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "2000",
                "full_name": f"Three Person {index}",
                "laureate_wikidata_qid": f"Q20{index}",
                "affiliation_name": "University Three",
                "affiliation_sub_name": f"Unit {letter}",
            }
            for index, letter in enumerate("ABC", start=1)
        )
        records.append(
            {
                "award_record_id": "unitless",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "2000",
                "full_name": "Unitless Person",
                "laureate_wikidata_qid": "Q301",
                "affiliation_name": "Unitless Institute",
            }
        )
        database = self.create_database(rankings, records)

        build.build_site(database, "https://example.org/", self.website)

        page = (self.website / "dist/affiliations/index.html").read_text()
        one_start = page.index('href="university-one/"')
        three_start = page.index('href="university-three/"')
        unitless_start = page.index('href="unitless-institute/"')
        one = page[one_start:three_start]
        three = page[three_start:unitless_start]
        unitless = page[unitless_start:page.index("</ol>", unitless_start)]

        visible, disclosure = one.split('<details class="rank-units-more">', 1)
        hidden = disclosure.split("</details>", 1)[0]
        self.assertLess(visible.index("Unit A"), visible.index("Unit B"))
        self.assertLess(visible.index("Unit B"), visible.index("Unit C"))
        self.assertNotIn("Unit D", visible)
        self.assertNotIn("Unit E", visible)
        self.assertIn("<summary>+ 2 more</summary>", hidden)
        self.assertLess(hidden.index("Unit D"), hidden.index("Unit E"))
        self.assertRegex(one, r'rank-count[^>]*>5<')

        self.assertNotIn("<details", three)
        self.assertLess(three.index("Unit A"), three.index("Unit B"))
        self.assertLess(three.index("Unit B"), three.index("Unit C"))
        self.assertNotIn("rank-units", unitless)
        self.assertNotIn("<details", unitless)
        self.assertRegex(unitless, r'rank-count[^>]*>1<')

    def test_university_pages_include_only_classified_universities(self) -> None:
        rankings = [("Q1", "Test Prize", "test-prize", "https://example.org/prize", 100)]
        records = [
            {
                "award_record_id": "university-one",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "2000",
                "full_name": "Alice Alpha",
                "laureate_wikidata_qid": "Q100",
                "affiliation_name": "University One",
                "affiliation_country": "United States",
                "affiliation_wikidata_qid": "Q10",
            },
            {
                "award_record_id": "institute-one",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "2001",
                "full_name": "Bob Beta",
                "laureate_wikidata_qid": "Q200",
                "affiliation_name": "Institute One",
                "affiliation_country": "United States",
                "affiliation_wikidata_qid": "Q20",
            },
            {
                "award_record_id": "university-two",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "2002",
                "full_name": "Carol Gamma",
                "laureate_wikidata_qid": "Q300",
                "affiliation_name": "University Two",
                "affiliation_country": "Belgium",
                "affiliation_wikidata_qid": "Q30",
            },
        ]
        database = self.create_database(
            rankings,
            records,
            profiles=[("Q10", "university"), ("Q20", "institute"), ("Q30", "university")],
        )

        build.build_site(database, "https://example.org/", self.website)

        overall = (self.website / "dist/universities/index.html").read_text()
        countries = (self.website / "dist/universities/countries/index.html").read_text()
        institutions = (self.website / "dist/affiliations/index.html").read_text()
        sitemap = (self.website / "dist/sitemap.xml").read_text()
        llms = (self.website / "dist/llms.txt").read_text()

        self.assertIn("Universities with the most award-winning laureates", overall)
        self.assertIn(">University One</a>", overall)
        self.assertIn(">University Two</a>", overall)
        self.assertNotIn(">Institute One</a>", overall)
        self.assertIn(">University One</a>", countries)
        self.assertIn(">University Two</a>", countries)
        self.assertNotIn(">Institute One</a>", countries)
        self.assertIn('href="../universities/">Universities</a>', institutions)
        self.assertIn("https://example.org/universities/", sitemap)
        self.assertIn("https://example.org/universities/countries/", sitemap)
        self.assertIn("[Universities](https://example.org/universities/)", llms)

    def test_subject_institutions_tab_ranks_by_in_subject_laureates(self) -> None:
        rankings = [("Q1", "Test Prize", "test-prize", "https://example.org/prize", 100)]
        records = [
            {
                "award_record_id": "bio-one",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "2000",
                "full_name": "Alice Alpha",
                "laureate_wikidata_qid": "Q100",
                "high_school_subject": "Biology",
                "affiliation_name": "University One",
                "affiliation_city": "Boston",
                "affiliation_country": "United States",
            },
            {
                "award_record_id": "bio-two",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "2001",
                "full_name": "Bob Beta",
                "laureate_wikidata_qid": "Q200",
                "high_school_subject": "Biology",
                "affiliation_name": "University One",
                "affiliation_city": "Boston",
                "affiliation_country": "United States",
            },
            {
                "award_record_id": "physics-one",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "2002",
                "full_name": "Carol Gamma",
                "laureate_wikidata_qid": "Q300",
                "high_school_subject": "Physics",
                "affiliation_name": "University One",
                "affiliation_city": "Boston",
                "affiliation_country": "United States",
            },
            {
                "award_record_id": "bio-three",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "2003",
                "full_name": "Dave Delta",
                "laureate_wikidata_qid": "Q400",
                "high_school_subject": "Biology",
                "affiliation_name": "Second Institute",
                "affiliation_city": "Oslo",
                "affiliation_country": "Norway",
            },
        ]
        database = self.create_database(rankings, records)

        build.build_site(database, "https://example.org/", self.website)

        biology = (self.website / "dist/subjects/biology/index.html").read_text()
        biology_institutions = (self.website / "dist/subjects/biology/affiliations/index.html").read_text()
        physics_institutions = (self.website / "dist/subjects/physics/affiliations/index.html").read_text()

        self.assertIn('href="affiliations/">Institutions</a>', biology)
        self.assertIn('href="../">People</a>', biology_institutions)
        self.assertIn('aria-current="page">Institutions</a>', biology_institutions)
        # Ranked by laureates within the subject, so the two-laureate institution leads.
        self.assertLess(
            biology_institutions.index(">University One</a>"),
            biology_institutions.index(">Second Institute</a>"),
        )
        self.assertRegex(biology_institutions, r"(?s)>University One</a>.*?rank-count[^>]*>2<")
        # The same institution holds one laureate in Physics, never its worldwide three.
        self.assertRegex(physics_institutions, r"(?s)>University One</a>.*?rank-count[^>]*>1<")
        self.assertIn("Boston, United States", biology_institutions)
        self.assertNotIn(">Second Institute</a>", physics_institutions)

    def test_subject_pages_and_badges(self) -> None:
        rankings = [("Q1", "Test Prize", "test-prize", "https://example.org/prize", 100)]
        records = [
            {
                "award_record_id": "math-alice",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "2000",
                "full_name": "Alice Alpha",
                "laureate_wikidata_qid": "Q100",
                "high_school_subject": "Math",
            },
            {
                "award_record_id": "computer-alice",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "2001",
                "full_name": "Alice Alpha",
                "laureate_wikidata_qid": "Q100",
                "high_school_subject": "CS",
            },
            {
                "award_record_id": "math-bob-one",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "2002",
                "full_name": "Bob Beta",
                "laureate_wikidata_qid": "Q200",
                "high_school_subject": "Math",
            },
            {
                "award_record_id": "math-bob-two",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "2003",
                "full_name": "Bob Beta",
                "laureate_wikidata_qid": "Q200",
                "high_school_subject": "Math",
            },
        ]
        database = self.create_database(rankings, records)

        plan = build.build_site(database, "https://example.org/awards/", self.website)

        self.assertEqual(2, plan.subject_count)
        index = (self.website / "dist/subjects/index.html").read_text()
        self.assertLess(index.index("Math"), index.index("CS"))
        math = (self.website / "dist/subjects/math/index.html").read_text()
        self.assertLess(math.index("Bob Beta"), math.index("Alice Alpha"))
        self.assertIn("2 awards", math)
        alice = (self.website / "dist/people/alice-alpha/index.html").read_text()
        self.assertIn('href="../../subjects/math/"', alice)
        self.assertIn('href="../../subjects/cs/"', alice)
        locations = [element.text for element in ElementTree.parse(self.website / "dist/sitemap.xml").getroot().findall(".//{*}loc")]
        self.assertIn("https://example.org/awards/subjects/", locations)
        self.assertIn("https://example.org/awards/subjects/math/", locations)
        self.assertIn("https://example.org/awards/subjects/cs/", locations)

    def test_subject_recent_pages_group_three_calendar_years_by_prize_and_recipient(self) -> None:
        rankings = [
            ("Q1", "Zeta Prize", "zeta-prize", "https://example.org/zeta", 100),
            ("Q2", "Alpha Prize", "alpha-prize", "https://example.org/alpha", 50),
        ]
        records = [
            {
                "award_record_id": "math-old",
                "award_wikidata_qid": "Q1",
                "prize_name": "Zeta Prize",
                "year": "2022",
                "full_name": "Old Recipient",
                "laureate_wikidata_qid": "Q100",
                "high_school_subject": "Math",
            },
            {
                "award_record_id": "math-2023",
                "award_wikidata_qid": "Q1",
                "prize_name": "Zeta Prize",
                "year": "2023",
                "full_name": "Third Year Recipient",
                "laureate_wikidata_qid": "Q200",
                "high_school_subject": "Math",
            },
            {
                "award_record_id": "math-2024",
                "award_wikidata_qid": "Q1",
                "prize_name": "Zeta Prize",
                "year": "2024",
                "full_name": "Second Year Recipient",
                "laureate_wikidata_qid": "Q300",
                "high_school_subject": "Math",
            },
            {
                "award_record_id": "math-alpha-a",
                "award_wikidata_qid": "Q2",
                "prize_name": "Alpha Prize",
                "year": "2025",
                "full_name": "Alice Alpha",
                "laureate_wikidata_qid": "Q400",
                "high_school_subject": "Math",
            },
            {
                "award_record_id": "math-alpha-b",
                "award_wikidata_qid": "Q2",
                "prize_name": "Alpha Prize",
                "year": "2025",
                "full_name": "Bob Beta",
                "laureate_wikidata_qid": "Q500",
                "high_school_subject": "Math",
            },
            {
                "award_record_id": "math-zeta",
                "award_wikidata_qid": "Q1",
                "prize_name": "Zeta Prize",
                "year": "2025",
                "full_name": "Zeta Recipient",
                "laureate_wikidata_qid": "Q600",
                "high_school_subject": "Math",
            },
            {
                "award_record_id": "physics-2010",
                "award_wikidata_qid": "Q1",
                "prize_name": "Zeta Prize",
                "year": "2010",
                "full_name": "Physics Recipient",
                "laureate_wikidata_qid": "Q700",
                "high_school_subject": "Physics",
            },
        ]
        database = self.create_database(rankings, records)

        build.build_site(database, "https://example.org/awards/", self.website)

        math = (self.website / "dist/subjects/math/index.html").read_text()
        recent = (self.website / "dist/subjects/math/recent/index.html").read_text()
        self.assertIn('href="recent/">Recent</a>', math)
        self.assertIn('href="../">People</a>', recent)
        self.assertIn('href="../affiliations/">Institutions</a>', recent)
        self.assertIn('aria-current="page">Recent</a>', recent)
        self.assertIn("5 recipients from", recent)
        self.assertIn("4 prize editions", recent)
        self.assertIn("2023–2025", recent)
        self.assertNotIn("Old Recipient", recent)

        year_2025 = recent.index("<h3>2025</h3>")
        year_2024 = recent.index("<h3>2024</h3>")
        year_2023 = recent.index("<h3>2023</h3>")
        self.assertLess(year_2025, year_2024)
        self.assertLess(year_2024, year_2023)
        latest = recent[year_2025:year_2024]
        self.assertLess(latest.index("Alpha Prize"), latest.index("Zeta Prize"))
        self.assertLess(latest.index("Alice Alpha"), latest.index("Bob Beta"))

        # Every populated subject gets the same Recent view, even when only one year falls inside its window.
        physics_recent = (self.website / "dist/subjects/physics/recent/index.html").read_text()
        self.assertIn("2008–2010", physics_recent)
        self.assertIn("Physics Recipient", physics_recent)

        locations = [
            element.text for element in ElementTree.parse(self.website / "dist/sitemap.xml").getroot().findall(".//{*}loc")
        ]
        self.assertIn("https://example.org/awards/subjects/math/recent/", locations)
        self.assertIn("https://example.org/awards/subjects/physics/recent/", locations)

    def test_invalid_subject_fails_the_build(self) -> None:
        rankings = [("Q1", "Test Prize", "test-prize", "https://example.org/prize", 100)]
        database = self.create_database(
            rankings,
            [
                {
                    "award_record_id": "record-1",
                    "award_wikidata_qid": "Q1",
                    "prize_name": "Test Prize",
                    "year": "2000",
                    "full_name": "Example Winner",
                    "high_school_subject": "Geography",
                }
            ],
        )

        with self.assertRaisesRegex(build.BuildFailure, "invalid subject record_id=record-1"):
            build.build_site(database, "https://example.org/", self.website)

    def test_missing_subject_fails_the_build(self) -> None:
        rankings = [("Q1", "Test Prize", "test-prize", "https://example.org/prize", 100)]
        database = self.create_database(
            rankings,
            [
                {
                    "award_record_id": "record-1",
                    "award_wikidata_qid": "Q1",
                    "prize_name": "Test Prize",
                    "year": "2000",
                    "full_name": "Example Winner",
                    "high_school_subject": "",
                }
            ],
        )

        with self.assertRaisesRegex(build.BuildFailure, "missing subject record_id=record-1"):
            build.build_site(database, "https://example.org/", self.website)

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
        self.assertIn('href="/awards/map/">Map</a>', error_html)
        self.assertNotIn("<link rel=\"canonical\"", error_html)

        # The error page is not a route: it must stay out of the sitemap and the page counts.
        root = ElementTree.parse(self.website / "dist/sitemap.xml").getroot()
        locations = [element.text for element in root.findall(".//{*}loc")]
        self.assertEqual(len(plan.jobs), len(locations))
        self.assertNotIn("https://example.org/awards/404.html", locations)

    def test_dataset_csv_dumps_every_award_and_is_linked_from_every_footer(self) -> None:
        rankings = [("Q1", "Test Prize", "test-prize", "https://example.org/prize", 100)]
        records = [
            {
                "award_record_id": "test-02",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "2001",
                "category": "Mathematics",
                "full_name": "Second Winner",
                "laureate_wikidata_qid": "Q10",
                "motivation": 'For saying "hello", clearly',
                "affiliation_name": "First Institute",
                "affiliation_country": "France",
                "affiliation_wikidata_qid": "Q2",
            },
            {
                "award_record_id": "test-01",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "2000",
                "category": "Physics",
                "full_name": "First Winner",
                "laureate_wikidata_qid": "Q11",
            },
        ]
        database = self.create_database(
            rankings,
            records,
            {"test-02": [{"affiliation_name": "Second Institute", "affiliation_country": "France"}]},
        )

        build.build_site(database, "https://example.org/awards/", self.website)

        with (self.website / "dist/awards.csv").open(newline="") as handle:
            rows = list(csv.reader(handle))
        self.assertEqual(list(build.AWARD_COLUMNS), rows[0])
        self.assertEqual(len(records), len(rows) - 1)
        self.assertEqual(["test-01", "test-02"], [row[0] for row in rows[1:]])
        self.assertEqual('For saying "hello", clearly', rows[2][build.AWARD_COLUMNS.index("motivation")])
        self.assertEqual("First Institute", rows[2][build.AWARD_COLUMNS.index("affiliation_name")])

        nested_html = (self.website / "dist/test-prize/physics/2000/index.html").read_text()
        self.assertIn('href="../../../awards.csv" download', nested_html)
        error_html = (self.website / "dist/404.html").read_text()
        self.assertIn('href="/awards/awards.csv" download', error_html)

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

    def test_winners_page_lists_every_recipient_oldest_first(self) -> None:
        rankings = [("Q1", "Test Prize", "test-prize", "https://example.org/prize", 100)]
        records = [
            {
                "award_record_id": f"record-{number}",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "category": category,
                "year": year,
                "full_name": name,
            }
            for number, (year, category, name) in enumerate(
                [
                    ("2001", "Physics", "Recent Winner"),
                    ("1950", "Physics", "Early Winner"),
                    ("1950", "Chemistry", "Other Early Winner"),
                ]
            )
        ]
        database = self.create_database(rankings, records)

        build.build_site(database, "https://example.org/awards/", self.website)

        winners = (self.website / "dist/test-prize/winners/index.html").read_text()
        self.assertIn("<h1>Test Prize: every winner</h1>", winners)
        self.assertIn("<h2>3 recipients, 1950-2001</h2>", winners)
        # Oldest first, and the category column appears because this prize routes by category.
        self.assertEqual(
            ["Early Winner", "Other Early Winner", "Recent Winner"],
            re.findall(r'<td><a href="[^"]*">([^<]*)</a></td>', winners),
        )
        self.assertEqual(["1950", "1950", "2001"], re.findall(r"<td>(\d{4})</td>", winners))
        self.assertIn('<td><a href="../physics/1950/early-winner/">Early Winner</a></td>', winners)

        # The prize page still stops at the recent years, so it has to point at the complete list.
        prize = (self.website / "dist/test-prize/index.html").read_text()
        self.assertIn('<a href="winners/">every Test Prize winner</a>', prize)

        locations = [
            element.text for element in ElementTree.parse(self.website / "dist/sitemap.xml").getroot().findall(".//{*}loc")
        ]
        self.assertIn("https://example.org/awards/test-prize/winners/", locations)

    def test_llms_txt_lists_every_prize_with_absolute_urls(self) -> None:
        rankings = [
            ("Q1", "Test Prize", "test-prize", "https://example.org/prize", 100),
            ("Q2", "Second Prize", "second-prize", "https://example.org/second", 40),
        ]
        records = [
            {
                "award_record_id": "one",
                "award_wikidata_qid": "Q1",
                "prize_name": "Test Prize",
                "year": "1950",
                "full_name": "Example Winner",
            },
            {
                "award_record_id": "two",
                "award_wikidata_qid": "Q2",
                "prize_name": "Second Prize",
                "year": "2000",
                "full_name": "Other Winner",
            },
        ]
        database = self.create_database(rankings, records)

        build.build_site(database, "https://example.org/awards/", self.website)

        llms = (self.website / "dist/llms.txt").read_text()
        self.assertTrue(llms.startswith("# Awards\n"))
        self.assertIn("1950-2000", llms)
        self.assertIn("https://example.org/awards/sitemap.xml", llms)
        # Highest score first, each prize named by its complete winner list and linked out to the awarding body.
        self.assertEqual(
            [
                "- [Every Test Prize winner](https://example.org/awards/test-prize/winners/): score 100/100. ",
                "- [Every Second Prize winner](https://example.org/awards/second-prize/winners/): score 40/100. ",
            ],
            [line[: line.index("Blurb.")] for line in llms.splitlines() if line.startswith("- [Every")],
        )
        self.assertIn("Awarding body: https://example.org/prize", llms)
        # Neither prize has categories here, so the by-year line must not promise any.
        self.assertIn("  - [Test Prize by year](https://example.org/awards/test-prize/): every award year\n", llms)
        # Every subject page is named explicitly.
        self.assertIn("- [Physics awards and laureates](https://example.org/awards/subjects/physics/): ", llms)
        self.assertIn("[Recent Physics prizes and recipients](https://example.org/awards/subjects/physics/recent/)", llms)
        # It is a guide to the site, not a page of it: no route, so no sitemap entry.
        locations = [
            element.text for element in ElementTree.parse(self.website / "dist/sitemap.xml").getroot().findall(".//{*}loc")
        ]
        self.assertNotIn("https://example.org/awards/llms.txt", locations)

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
        staging_modes: list[int] = []

        def executor(*args: object, **kwargs: object) -> object:
            workers.append(kwargs["max_workers"])
            return real_executor(*args, **kwargs)

        def fail_render(_environment: object, staging: Path, *_args: object) -> None:
            staging_modes.append(stat.S_IMODE(staging.stat().st_mode))
            raise RuntimeError("render failed")

        with (
            mock.patch.object(build, "ThreadPoolExecutor", side_effect=executor),
            mock.patch.object(build, "_render_job", side_effect=fail_render),
            self.assertRaises(RuntimeError),
        ):
            build.build_site(database, "https://example.org/", self.website)

        self.assertEqual([8], workers)
        self.assertEqual({0o2775}, set(staging_modes))
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
