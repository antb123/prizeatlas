from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import lookup_coordinates as lookup


def statement(longitude: float, latitude: float, rank: str = "normal", globe: str = "http://www.wikidata.org/entity/Q2") -> dict:
    return {
        "rank": rank,
        "mainsnak": {
            "datavalue": {
                "value": {
                    "longitude": longitude,
                    "latitude": latitude,
                    "globe": globe,
                },
            },
        },
    }


def entity(qid: str, longitude: float, latitude: float) -> dict:
    return {
        "id": qid,
        "labels": {"en": {"value": qid}},
        "descriptions": {"en": {"value": "test place"}},
        "claims": {"P625": [statement(longitude, latitude)]},
    }


class CoordinateLookupTests(unittest.TestCase):
    def test_preferred_coordinate_wins(self) -> None:
        item = {
            "claims": {
                "P625": [
                    statement(-1.0, 1.0),
                    statement(-71.09211, 42.35982, rank="preferred"),
                ],
            },
        }
        self.assertEqual([(-71.09211, 42.35982)], lookup.best_coordinates(item))

    def test_deprecated_and_non_earth_coordinates_are_ignored(self) -> None:
        item = {
            "claims": {
                "P625": [
                    statement(-1.0, 1.0, rank="deprecated"),
                    statement(20.0, 10.0, globe="http://www.wikidata.org/entity/Q111"),
                ],
            },
        }
        self.assertEqual([], lookup.best_coordinates(item))

    def test_search_ambiguity_requires_a_qid(self) -> None:
        entities = {
            "Q1": entity("Q1", -71.0, 42.0),
            "Q2": entity("Q2", -72.0, 43.0),
        }
        with (
            patch.object(lookup, "wikipedia_qid", return_value=None),
            patch.object(lookup, "search_qids", return_value=["Q1", "Q2"]),
            patch.object(lookup, "get_entities", return_value=entities),
        ):
            with self.assertRaisesRegex(lookup.LookupFailure, "ambiguous query"):
                lookup.resolve("Example")

    def test_geojson_is_longitude_then_latitude(self) -> None:
        item = entity("Q49108", -71.09211, 42.35982)
        feature = lookup.geojson_feature("MIT", "Q49108", item, (-71.09211, 42.35982), "wikipedia-title")
        self.assertEqual([-71.0921, 42.3598], feature["geometry"]["coordinates"])
        self.assertEqual("-71.0921,42.3598", feature["properties"]["dataset_coordinates"])

    def test_qid_lookup_is_not_rejected_by_country_bounds(self) -> None:
        item = entity("Q1297", -87.6298, 41.8781)
        stdout = io.StringIO()
        with patch.object(lookup, "resolve", return_value=("Q1297", item, (-87.6298, 41.8781), "qid")) as resolve:
            with redirect_stdout(stdout):
                result = lookup.main(["Q1297", "--country", "France"])

        self.assertEqual(0, result)
        resolve.assert_called_once_with("Q1297")
        self.assertIn('"dataset_coordinates": "-87.6298,41.8781"', stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
