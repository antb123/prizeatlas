#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sqlite3
import stat
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("build.py")
SPEC = importlib.util.spec_from_file_location("map_mvp_build", MODULE_PATH)
assert SPEC and SPEC.loader
build = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = build
SPEC.loader.exec_module(build)


class MapBuildTests(unittest.TestCase):
    def row(self, **values: str) -> sqlite3.Row:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        columns = (
            "award_record_id", "year", "high_school_subject", "birth_city", "birth_country", "birth_coordinates",
            "affiliation_name", "affiliation_city", "affiliation_country", "affiliation_coordinates",
        )
        connection.execute(f"CREATE TABLE row ({', '.join(columns)})")
        connection.execute(
            f"INSERT INTO row VALUES ({', '.join('?' for _ in columns)})",
            tuple(values.get(column, "") for column in columns),
        )
        result = connection.execute("SELECT * FROM row").fetchone()
        connection.close()
        return result

    def test_coordinate_validation(self) -> None:
        self.assertEqual((build.Point(-73.9, 40.7),), build.parse_points("-73.9,40.7", "r1", "birth_coordinates", False))
        self.assertEqual(
            (build.Point(-73.9, 40.7), build.Point(2.1, 48.6)),
            build.parse_points("-73.9,40.7;2.1,48.6", "r1", "affiliation_coordinates", True),
        )
        for value in ("181,0", "0,91", "nan,0", "1", "1,2,3", "1,2;3,4"):
            with self.subTest(value=value), self.assertRaises(build.BuildError):
                build.parse_points(value, "safe-id", "birth_coordinates", False)

    def test_aggregation_counts_each_affiliation_coordinate(self) -> None:
        rows = [
            self.row(
                award_record_id="r1",
                year="1999",
                high_school_subject="Math",
                birth_city="Paris",
                birth_country="France",
                birth_coordinates="2.35,48.86",
                affiliation_name="Two institutes",
                affiliation_city="Paris; Boston",
                affiliation_country="France; United States",
                affiliation_coordinates="2.35,48.86;-71.06,42.36",
            ),
            self.row(
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
        ]
        markers = build.aggregate(rows)
        self.assertEqual(1, len(markers["birth"]))
        self.assertEqual(2, markers["birth"][0]["count"])
        self.assertEqual({"Math": 1, "Physics": 1}, markers["birth"][0]["subjects"])
        self.assertEqual({"1990s": 1, "2000s": 1}, markers["birth"][0]["decades"])
        self.assertEqual({"1990s": 1}, markers["birth"][0]["subject_decades"]["Math"])
        self.assertEqual(2, len(markers["affiliation"]))
        self.assertEqual([1, 2], sorted(marker["count"] for marker in markers["affiliation"]))
        paris = next(marker for marker in markers["affiliation"] if marker["count"] == 2)
        self.assertEqual(1, paris["extra_labels"])

    def test_blank_birth_city_uses_country_display_only(self) -> None:
        markers = build.aggregate([
            self.row(
                award_record_id="r1",
                year="2024",
                high_school_subject="Biology",
                birth_country="Belgium",
                birth_coordinates="4.35,50.85",
            )
        ])
        marker = markers["birth"][0]
        self.assertEqual("", marker["city"])
        self.assertEqual("Belgium", marker["title"])

    def test_safe_serialization(self) -> None:
        encoded = build.compact_json({"title": "</script>"})
        self.assertNotIn("<", encoded)
        self.assertEqual("</script>", json.loads(encoded)["title"])

    def test_real_template_and_atomic_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "awards.sqlite3"
            with sqlite3.connect(database) as connection:
                connection.execute(
                    """
                    CREATE TABLE awards (
                        award_record_id TEXT,
                        year TEXT,
                        high_school_subject TEXT,
                        birth_city TEXT,
                        birth_country TEXT,
                        birth_coordinates TEXT,
                        affiliation_name TEXT,
                        affiliation_city TEXT,
                        affiliation_country TEXT,
                        affiliation_coordinates TEXT
                    )
                    """
                )
                connection.execute(
                    "INSERT INTO awards VALUES ('r1', '2024', 'Physics', 'Tokyo', 'Japan', '139.69,35.69', "
                    "'Example University', 'Tokyo', 'Japan', '139.70,35.68')"
                )
            output = root / "dist" / "index.html"
            build.build(database, Path(__file__).with_name("template.html"), output)
            document = output.read_text(encoding="utf-8")
            self.assertEqual(0o644, stat.S_IMODE(output.stat().st_mode))
            self.assertNotIn("__MAP_DATA__", document)
            self.assertIn("leaflet@1.9.4", document)
            self.assertIn("sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=", document)
            self.assertIn("tile.openstreetmap.org", document)
            self.assertIn("Birthplaces", document)
            self.assertIn("Institutions", document)
            self.assertIn("Surprise me", document)
            self.assertIn("2.5 * Math.sqrt(marker.count)", document)
            self.assertIn('bindToggle("affiliation", "institution")', document)
            self.assertIn('role="region"', document)
            self.assertTrue((output.parent / "physics" / "index.html").is_file())
            self.assertEqual("earth-science", build.subject_slug("Earth Science"))


if __name__ == "__main__":
    unittest.main()
