#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["shapely>=2,<3"]
# ///
"""Verify a longitude,latitude point against locally stored country polygons.

This command never makes a network request. Download the Natural Earth Admin-0
Countries GeoJSON once before use:

    curl -fL -o data/ne_10m_admin_0_countries.geojson \\
      https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_0_countries.geojson
    curl -fL -o data/ne_50m_populated_places.geojson \\
      https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_populated_places.geojson

Run from datasets/:

    uv run scripts/check_country.py --coordinates 2.3522,48.8566 --expect FR \\
      --city Paris --city-country FR --within-km 20
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

from shapely import make_valid
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

DEFAULT_DATA = Path(__file__).resolve().parents[1] / "data" / "ne_10m_admin_0_countries.geojson"
DEFAULT_CITIES_DATA = Path(__file__).resolve().parents[1] / "data" / "ne_50m_populated_places.geojson"


def parse_coordinates(value: str) -> tuple[float, float]:
    """Return longitude, latitude from the dataset coordinate format."""
    parts = value.split(",")
    if len(parts) != 2:
        raise ValueError("coordinates must be longitude,latitude")
    longitude, latitude = (float(part.strip()) for part in parts)
    if not math.isfinite(longitude) or not math.isfinite(latitude):
        raise ValueError("coordinates must be finite numbers")
    if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        raise ValueError("coordinates are outside WGS84 bounds")
    return longitude, latitude


def first_property(properties: dict[str, Any], *keys: str) -> str | None:
    """Return the first usable Natural Earth property."""
    for key in keys:
        value = properties.get(key)
        if value not in (None, "", "-99", -99):
            return str(value)
    return None


def country_details(properties: dict[str, Any]) -> dict[str, Any]:
    """Return stable country fields and all original boundary attributes."""
    return {
        "name": first_property(properties, "ADMIN", "NAME_EN", "NAME_LONG", "NAME"),
        "formal_name": first_property(properties, "FORMAL_EN"),
        "sovereign": first_property(properties, "SOVEREIGNT"),
        "iso2": first_property(properties, "ISO_A2_EH", "ISO_A2"),
        "iso3": first_property(properties, "ISO_A3_EH", "ISO_A3", "ADM0_A3"),
        "continent": first_property(properties, "CONTINENT"),
        "un_region": first_property(properties, "REGION_UN"),
        "subregion": first_property(properties, "SUBREGION"),
        "properties": properties,
    }


def expected_matches(country: dict[str, Any], expected: str) -> bool:
    """Match a country name or code without guessing from partial text."""
    candidate_values = list(country.values())
    candidate_values.extend(country["properties"].values())
    expected = expected.strip().casefold()
    return any(str(value).strip().casefold() == expected for value in candidate_values if value is not None)


def haversine_km(longitude: float, latitude: float, other_longitude: float, other_latitude: float) -> float:
    """Return the great-circle distance between two WGS84 coordinates."""
    latitude_delta = math.radians(other_latitude - latitude)
    longitude_delta = math.radians(other_longitude - longitude)
    latitude = math.radians(latitude)
    other_latitude = math.radians(other_latitude)
    a = math.sin(latitude_delta / 2) ** 2 + math.cos(latitude) * math.cos(other_latitude) * math.sin(longitude_delta / 2) ** 2
    return 6371.0088 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class CountryIndex:
    """An in-memory point-in-country index built from one local GeoJSON file."""

    def __init__(self, data_path: Path) -> None:
        try:
            document = json.loads(data_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise ValueError(f"boundary data not found: {data_path}") from error
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid GeoJSON: {data_path}: {error}") from error

        features = document.get("features")
        if document.get("type") != "FeatureCollection" or not isinstance(features, list):
            raise ValueError("boundary data must be a GeoJSON FeatureCollection")

        self.geometries: list[Any] = []
        self.countries: list[dict[str, Any]] = []
        for feature in features:
            geometry_data = feature.get("geometry")
            if not geometry_data:
                continue
            geometry = shape(geometry_data)
            if geometry.is_empty:
                continue
            if not geometry.is_valid:
                geometry = make_valid(geometry)
            self.geometries.append(geometry)
            self.countries.append(country_details(dict(feature.get("properties") or {})))

        if not self.geometries:
            raise ValueError("boundary data has no usable country polygons")
        self.tree = STRtree(self.geometries)

    def find(self, longitude: float, latitude: float) -> list[dict[str, Any]]:
        """Return every country polygon covering the coordinate."""
        point = Point(longitude, latitude)
        matches = [
            self.countries[int(index)]
            for index in self.tree.query(point)
            if self.geometries[int(index)].covers(point)
        ]
        return sorted(matches, key=lambda country: (country["name"] or "", country["iso3"] or ""))

    def matches_expected(self, countries: list[dict[str, Any]], expected: str) -> bool:
        """Match the expected country directly or through its sovereign state."""
        expected_sovereigns = {
            country["sovereign"]
            for country in self.countries
            if country["sovereign"] and expected_matches(country, expected)
        }
        return any(expected_matches(country, expected) or country["sovereign"] in expected_sovereigns for country in countries)


def city_details(properties: dict[str, Any], longitude: float, latitude: float) -> dict[str, Any]:
    """Return stable city fields and all original Natural Earth attributes."""
    return {
        "name": first_property(properties, "NAME", "NAME_EN", "NAMEASCII"),
        "country": first_property(properties, "ADM0NAME", "SOV0NAME"),
        "iso2": first_property(properties, "ISO_A2"),
        "iso3": first_property(properties, "ADM0_A3", "SOV_A3"),
        "admin1": first_property(properties, "ADM1NAME"),
        "feature": first_property(properties, "FEATURECLA"),
        "coordinates": f"{longitude},{latitude}",
        "properties": properties,
    }


def city_country_matches(city: dict[str, Any], country: str | None) -> bool:
    """Match an optional city country name or ISO code exactly."""
    if country is None:
        return True
    expected = country.strip().casefold()
    return any(str(value).strip().casefold() == expected for value in city.values() if value is not None)


class CityIndex:
    """A small local index of Natural Earth's major global populated places."""

    def __init__(self, data_path: Path) -> None:
        try:
            document = json.loads(data_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise ValueError(f"city data not found: {data_path}") from error
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid city GeoJSON: {data_path}: {error}") from error

        features = document.get("features")
        if document.get("type") != "FeatureCollection" or not isinstance(features, list):
            raise ValueError("city data must be a GeoJSON FeatureCollection")

        self.cities: list[dict[str, Any]] = []
        for feature in features:
            geometry = feature.get("geometry")
            coordinates = geometry.get("coordinates") if isinstance(geometry, dict) and geometry.get("type") == "Point" else None
            if not isinstance(coordinates, list) or len(coordinates) < 2:
                continue
            longitude, latitude = coordinates[:2]
            if not isinstance(longitude, (int, float)) or not isinstance(latitude, (int, float)):
                continue
            self.cities.append(city_details(dict(feature.get("properties") or {}), longitude, latitude))

        if not self.cities:
            raise ValueError("city data has no usable point features")

    def nearby(self, name: str, country: str | None, longitude: float, latitude: float, radius_km: float) -> list[dict[str, Any]]:
        """Return named cities in the requested radius, nearest first."""
        expected_name = name.strip().casefold()
        matches: list[dict[str, Any]] = []
        for city in self.cities:
            city_names = (city["name"], city["properties"].get("NAME_EN"), city["properties"].get("NAMEASCII"))
            if not any(isinstance(value, str) and value.strip().casefold() == expected_name for value in city_names):
                continue
            if not city_country_matches(city, country):
                continue
            city_longitude, city_latitude = (float(value) for value in city["coordinates"].split(","))
            distance_km = haversine_km(longitude, latitude, city_longitude, city_latitude)
            if distance_km <= radius_km:
                matches.append({"distance_km": round(distance_km, 3), "city": city})
        return sorted(matches, key=lambda match: match["distance_km"])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--coordinates" in arguments:
        position = arguments.index("--coordinates")
        if position + 1 < len(arguments) and arguments[position + 1].startswith("-"):
            arguments[position] = f"--coordinates={arguments[position + 1]}"
            del arguments[position + 1]

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coordinates", required=True, help="longitude,latitude in WGS84")
    parser.add_argument("--expect", help="Expected country name, ISO-2, or ISO-3 code")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="Local country GeoJSON")
    parser.add_argument("--city", help="Optional major city name to verify")
    parser.add_argument("--city-country", help="Optional city country name, ISO-2, or ISO-3 code")
    parser.add_argument("--within-km", type=float, default=20, help="Maximum distance from --city (default: 20)")
    parser.add_argument("--cities-data", type=Path, default=DEFAULT_CITIES_DATA, help="Local populated-places GeoJSON")
    return parser.parse_args(arguments)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        longitude, latitude = parse_coordinates(args.coordinates)
        country_index = CountryIndex(args.data)
        countries = country_index.find(longitude, latitude)
        if args.city_country and not args.city:
            raise ValueError("--city-country requires --city")
        if args.within_km <= 0:
            raise ValueError("--within-km must be greater than zero")
    except (OSError, TypeError, ValueError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 2

    result: dict[str, Any] = {
        "coordinates": f"{longitude},{latitude}",
        "longitude": longitude,
        "latitude": latitude,
        "status": "outside_all_country_polygons" if not countries else "inside" if len(countries) == 1 else "boundary_overlap_or_disputed_area",
        "inside_any_country_polygon": bool(countries),
        "countries": countries,
    }
    verified = bool(countries)
    if args.expect:
        verified = verified and country_index.matches_expected(countries, args.expect)
        result["expected"] = args.expect
        result["country_verified"] = verified
    if args.city:
        try:
            city_matches = CityIndex(args.cities_data).nearby(args.city, args.city_country, longitude, latitude, args.within_km)
        except (OSError, TypeError, ValueError) as error:
            print(json.dumps({"error": str(error)}), file=sys.stderr)
            return 2
        city_verified = bool(city_matches)
        verified = verified and city_verified
        result["city"] = {"expected": args.city, "expected_country": args.city_country, "within_km": args.within_km, "matches": city_matches}
        result["city_verified"] = city_verified
    if args.expect or args.city:
        result["verified"] = verified

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
