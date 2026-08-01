# SPDX-License-Identifier: GPL-2.0-or-later
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
        self.assertIsNone(chk.parse_stored_coordinates("nan,2"))
        self.assertIsNone(chk.parse_stored_coordinates("181,2"))
        self.assertIsNone(chk.parse_stored_coordinates("2,91"))


class CheckAllTests(unittest.TestCase):
    def _make_db(self, rows: list[tuple[str, str, str, str, str]], extras: list[tuple[str, int, str, str, str, str]] = []) -> str:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        tmp.close()
        con = sqlite3.connect(tmp.name)
        con.execute(
            "CREATE TABLE awards ("
            "award_record_id TEXT, affiliation_name TEXT, affiliation_city TEXT, "
            "affiliation_country TEXT, affiliation_coordinates TEXT)"
        )
        con.execute(
            "CREATE TABLE award_extra_affiliations ("
            "award_record_id TEXT, position INTEGER, affiliation_name TEXT, affiliation_city TEXT, "
            "affiliation_country TEXT, affiliation_coordinates TEXT)"
        )
        for record_id, name, city, country, coords in rows:
            con.execute(
                "INSERT INTO awards VALUES (?, ?, ?, ?, ?)",
                (record_id, name, city, country, coords),
            )
        for record_id, position, name, city, country, coords in extras:
            con.execute(
                "INSERT INTO award_extra_affiliations VALUES (?, ?, ?, ?, ?, ?)",
                (record_id, position, name, city, country, coords),
            )
        con.commit()
        con.close()
        return tmp.name

    def test_groups_both_stores_and_accepts_distinct_city_points(self) -> None:
        db = self._make_db([
            ("r1", "Collège de France", "Paris", "France", "2.3456,48.8492"),
        ], [
            ("r1", 2, "Institut Pasteur", "Paris", "France", "2.3320,48.8560"),
            ("r2", 2, "MIT", "Cambridge", "United States", "-71.0919,42.3597"),
        ])

        cache_path = Path(tempfile.mktemp(suffix=".json"))
        output_path = Path(tempfile.mktemp(suffix=".json"))

        def fake_city(city, country, cache, cache_path, rate_limit=1.0):
            if city == "Paris":
                return [{"lon": "2.35", "lat": "48.85"}]
            return [{"lon": "-71.09", "lat": "42.36"}]

        with patch.object(chk, "nominatim_city_search", side_effect=fake_city):
            summary = chk.check_all(db, cache_path, output_path)

        self.assertEqual(2, summary["total"])
        self.assertEqual(2, summary["verified"])
        self.assertEqual(2, summary["MATCH"])

        report = json.loads(output_path.read_text())
        self.assertEqual("MATCH", report["results"][0]["status"])
        self.assertEqual(2, len(report["results"][1]["stored_points"]))

        Path(db).unlink()
        cache_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)

    def test_reports_missing_invalid_inverted_discrepancy_and_lookup_failure(self) -> None:
        db = self._make_db([
            ("r1", "Missing", "Blank", "France", ""),
            ("r2", "Invalid", "Bad", "France", "1,91"),
            ("r3", "Inverted", "Paris", "France", "48.85,2.35"),
            ("r4", "Wrong", "Lyon", "France", "2.35,48.85"),
            ("r5", "Unknown", "Nowhere", "Narnia", "10.0,20.0"),
        ])
        cache_path = Path(tempfile.mktemp(suffix=".json"))
        output_path = Path(tempfile.mktemp(suffix=".json"))

        def fake_city(city, country, cache, cache_path, rate_limit=1.0):
            if city == "Nowhere":
                return []
            if city == "Lyon":
                return [{"lon": "4.8357", "lat": "45.7640"}]
            return [{"lon": "2.35", "lat": "48.85"}]

        with patch.object(chk, "nominatim_city_search", side_effect=fake_city):
            summary = chk.check_all(db, cache_path, output_path)

        self.assertEqual(5, summary["total"])
        self.assertEqual(0, summary["verified"])
        self.assertEqual(1, summary["MISSING_COORDINATES"])
        self.assertEqual(1, summary["INVALID_COORDINATES"])
        self.assertEqual(1, summary["INVERTED"])
        self.assertEqual(1, summary["DISCREPANCY"])
        self.assertEqual(1, summary["LOOKUP_FAILED"])

        Path(db).unlink()
        cache_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)

    def test_main_returns_nonzero_when_not_every_pair_is_verified(self) -> None:
        db = self._make_db([("r1", "Missing", "Blank", "France", "")])
        cache_path = Path(tempfile.mktemp(suffix=".json"))
        output_path = Path(tempfile.mktemp(suffix=".json"))

        self.assertEqual(1, chk.main(["--db", db, "--cache", str(cache_path), "--output", str(output_path)]))

        Path(db).unlink()
        cache_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
