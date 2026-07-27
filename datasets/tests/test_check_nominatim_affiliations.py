from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import check_nominatim_affiliations as chk


class HaversineTests(unittest.TestCase):
    def test_same_point_is_zero(self) -> None:
        self.assertAlmostEqual(0.0, chk.haversine_km(2.35, 48.85, 2.35, 48.85))

    def test_known_distance(self) -> None:
        self.assertAlmostEqual(660, chk.haversine_km(2.35, 48.85, 5.37, 43.30), delta=10)


class DegreeDeltaTests(unittest.TestCase):
    def test_zero_for_same_point(self) -> None:
        self.assertEqual(0.0, chk.degree_delta(1.0, 2.0, 1.0, 2.0))

    def test_diagonal(self) -> None:
        self.assertAlmostEqual(math.sqrt(2), chk.degree_delta(0.0, 0.0, 1.0, 1.0))


import math


class ClassifyTests(unittest.TestCase):
    def test_match_within_threshold(self) -> None:
        self.assertEqual("MATCH", chk.classify(2.3456, 48.8492, 2.35, 48.85))

    def test_discrepancy_beyond_threshold(self) -> None:
        self.assertEqual("DISCREPANCY", chk.classify(2.3456, 48.8492, 5.0, 50.0))

    def test_inverted_coordinates_detected(self) -> None:
        self.assertEqual("INVERTED", chk.classify(48.8492, 2.3456, 2.35, 48.85))


class ParseCoordinatesTests(unittest.TestCase):
    def test_valid(self) -> None:
        self.assertEqual((2.3456, 48.8492), chk.parse_stored_coordinates("2.3456,48.8492"))

    def test_negative(self) -> None:
        self.assertEqual((-71.0919, 42.3597), chk.parse_stored_coordinates("-71.0919,42.3597"))

    def test_invalid_returns_none(self) -> None:
        self.assertIsNone(chk.parse_stored_coordinates("bad"))
        self.assertIsNone(chk.parse_stored_coordinates("1,2,3"))


class CheckAllTests(unittest.TestCase):
    def _make_db(self, rows: list[tuple[str, str, str, str]]) -> str:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        tmp.close()
        con = sqlite3.connect(tmp.name)
        con.execute(
            "CREATE TABLE awards ("
            "award_record_id TEXT, affiliation_name TEXT, affiliation_city TEXT, "
            "affiliation_country TEXT, affiliation_coordinates TEXT)"
        )
        for record_id, name, city, country, coords in rows:
            con.execute(
                "INSERT INTO awards VALUES (?, ?, ?, ?, ?)",
                (record_id, name, city, country, coords),
            )
        con.commit()
        con.close()
        return tmp.name

    def test_match_and_not_found(self) -> None:
        db = self._make_db([
            ("r1", "Collège de France", "Paris", "France", "2.3456,48.8492"),
            ("r2", "Unknown Place", "Nowhere", "Narnia", "10.0,20.0"),
        ])

        cache_path = Path(tempfile.mktemp(suffix=".json"))
        output_path = Path(tempfile.mktemp(suffix=".json"))

        def fake_search(query, cache, cache_path, rate_limit=1.0):
            if "Collège" in query:
                return [{"lon": "2.35", "lat": "48.85"}]
            return []

        def fake_city(city, country, cache, cache_path, rate_limit=1.0):
            if country == "Narnia":
                return []
            return []

        with (
            patch.object(chk, "nominatim_search", side_effect=fake_search),
            patch.object(chk, "nominatim_city_search", side_effect=fake_city),
        ):
            summary = chk.check_all(db, cache_path, output_path)

        self.assertEqual(2, summary["total"])
        self.assertEqual(1, summary["MATCH"])
        self.assertEqual(1, summary["NOT_FOUND"])

        report = json.loads(output_path.read_text())
        self.assertEqual("MATCH", report["results"][0]["status"])
        self.assertEqual("NOT_FOUND", report["results"][1]["status"])

        Path(db).unlink()
        cache_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
