from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import check_country


def write_boundaries(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"ADMIN": "France", "ISO_A2": "FR", "ISO_A3": "FRA", "CONTINENT": "Europe"},
                        "geometry": {"type": "Polygon", "coordinates": [[[0, 40], [10, 40], [10, 50], [0, 50], [0, 40]]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "ADMIN": "United States of America",
                            "NAME_LONG": "United States",
                            "SOVEREIGNT": "United States of America",
                            "ISO_A2": "US",
                            "ISO_A3": "USA",
                        },
                        "geometry": {"type": "Polygon", "coordinates": [[[-110, 30], [-100, 30], [-100, 40], [-110, 40], [-110, 30]]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"ADMIN": "Puerto Rico", "SOVEREIGNT": "United States of America", "ISO_A2": "PR", "ISO_A3": "PRI"},
                        "geometry": {"type": "Polygon", "coordinates": [[[-70, 15], [-60, 15], [-60, 20], [-70, 20], [-70, 15]]]},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def write_cities(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"NAME": "Paris", "NAME_EN": "Paris", "ISO_A2": "FR", "ADM0_A3": "FRA", "ADM0NAME": "France"},
                        "geometry": {"type": "Point", "coordinates": [2.353, 48.858]},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


class CheckCountryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.boundaries = Path(tempfile.mktemp(suffix=".geojson"))
        self.cities = Path(tempfile.mktemp(suffix=".geojson"))
        write_boundaries(self.boundaries)
        write_cities(self.cities)

    def tearDown(self) -> None:
        self.boundaries.unlink()
        self.cities.unlink()

    def test_parse_coordinates_uses_longitude_latitude_order(self) -> None:
        self.assertEqual((2.3522, 48.8566), check_country.parse_coordinates("2.3522,48.8566"))
        with self.assertRaisesRegex(ValueError, "longitude,latitude"):
            check_country.parse_coordinates("48.8566")

    def test_parse_args_accepts_negative_longitude(self) -> None:
        args = check_country.parse_args(["--coordinates", "-66.0506,18.4031"])
        self.assertEqual("-66.0506,18.4031", args.coordinates)

    def test_find_returns_country_and_all_boundary_properties(self) -> None:
        country = check_country.CountryIndex(self.boundaries).find(2.3522, 48.8566)[0]
        self.assertEqual("France", country["name"])
        self.assertEqual("FR", country["iso2"])
        self.assertEqual("FRA", country["iso3"])
        self.assertEqual("Europe", country["properties"]["CONTINENT"])

    def test_main_verifies_expected_country(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            status = check_country.main(["--coordinates", "2.3522,48.8566", "--expect", "FR", "--data", str(self.boundaries)])
        result = json.loads(stdout.getvalue())
        self.assertEqual(0, status)
        self.assertTrue(result["verified"])

    def test_main_reports_mismatch_and_outside_point(self) -> None:
        with redirect_stdout(io.StringIO()):
            self.assertEqual(1, check_country.main(["--coordinates", "2.3522,48.8566", "--expect", "DE", "--data", str(self.boundaries)]))
            self.assertEqual(1, check_country.main(["--coordinates", "20,60", "--data", str(self.boundaries)]))

    def test_expected_sovereign_matches_territory(self) -> None:
        index = check_country.CountryIndex(self.boundaries)
        self.assertTrue(index.matches_expected(index.find(-66, 18), "United States"))

    def test_main_verifies_city_radius_and_country(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            status = check_country.main(
                [
                    "--coordinates", "2.3522,48.8566", "--expect", "FR", "--city", "Paris", "--city-country", "FR", "--within-km", "20",
                    "--data", str(self.boundaries), "--cities-data", str(self.cities),
                ]
            )
        result = json.loads(stdout.getvalue())
        self.assertEqual(0, status)
        self.assertTrue(result["city_verified"])
        self.assertLess(result["city"]["matches"][0]["distance_km"], 1)

    def test_main_reports_city_outside_radius(self) -> None:
        with redirect_stdout(io.StringIO()):
            status = check_country.main(
                [
                    "--coordinates", "3,48.8566", "--city", "Paris", "--city-country", "FR", "--within-km", "20",
                    "--data", str(self.boundaries), "--cities-data", str(self.cities),
                ]
            )
        self.assertEqual(1, status)

    def test_boundary_point_is_inside(self) -> None:
        countries = check_country.CountryIndex(self.boundaries).find(0, 40)
        self.assertEqual(["France"], [country["name"] for country in countries])


if __name__ == "__main__":
    unittest.main()
