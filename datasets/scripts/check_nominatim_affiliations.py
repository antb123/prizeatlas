#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Check affiliation_coordinates in awards.sqlite3 against OpenStreetMap Nominatim."""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "PrizeAtlas-nominatim-affiliation-check/1.0 (https://prizeatlas.org/)"
MATCH_DEGREES = 0.3
RATE_LIMIT = 1.0


def haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def degree_delta(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    return math.sqrt((lon2 - lon1) ** 2 + (lat2 - lat1) ** 2)


def load_cache(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text())
    return {}


def save_cache(path: Path, cache: dict[str, Any]) -> None:
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2))


def nominatim_city_search(city: str, country: str, cache: dict[str, Any], cache_path: Path, rate_limit: float = RATE_LIMIT) -> list[dict[str, Any]]:
    key = f"city:{city}|{country}"
    if key in cache:
        return cache[key]

    params = urllib.parse.urlencode({"city": city, "country": country, "format": "jsonv2", "limit": 1})
    request = urllib.request.Request(
        f"{NOMINATIM_URL}?{params}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            results = json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        results = []

    cache[key] = results
    save_cache(cache_path, cache)
    time.sleep(rate_limit)
    return results


def parse_stored_coordinates(value: str) -> tuple[float, float] | None:
    if not isinstance(value, str):
        return None
    parts = value.strip().split(",")
    if len(parts) != 2:
        return None
    try:
        longitude, latitude = float(parts[0].strip()), float(parts[1].strip())
    except ValueError:
        return None
    if not math.isfinite(longitude) or not math.isfinite(latitude):
        return None
    if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        return None
    return longitude, latitude


def classify(stored_lon: float, stored_lat: float, nominatim_lon: float, nominatim_lat: float) -> str:
    delta = degree_delta(stored_lon, stored_lat, nominatim_lon, nominatim_lat)
    if delta <= MATCH_DEGREES:
        return "MATCH"
    inverted_delta = degree_delta(stored_lon, stored_lat, nominatim_lat, nominatim_lon)
    if inverted_delta <= MATCH_DEGREES:
        return "INVERTED"
    return "DISCREPANCY"


def fetch_affiliations(db_path: str) -> list[dict[str, Any]]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT award_record_id, 1 AS position, affiliation_name, affiliation_city, affiliation_country, affiliation_coordinates "
        "FROM awards "
        "UNION ALL "
        "SELECT award_record_id, position, affiliation_name, affiliation_city, affiliation_country, affiliation_coordinates "
        "FROM award_extra_affiliations"
    ).fetchall()
    con.close()
    return [dict(row) for row in rows]


def check_all(db_path: str, cache_path: Path, output_path: Path) -> dict[str, Any]:
    cache = load_cache(cache_path)
    rows = fetch_affiliations(db_path)

    pairs: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        city = (row["affiliation_city"] or "").strip()
        country = (row["affiliation_country"] or "").strip()
        if city and country:
            pairs.setdefault((city, country), []).append(row)

    results: list[dict[str, Any]] = []
    counts = {"MATCH": 0, "MISSING_COORDINATES": 0, "INVALID_COORDINATES": 0, "LOOKUP_FAILED": 0, "DISCREPANCY": 0, "INVERTED": 0}

    for i, ((city, country), entries) in enumerate(sorted(pairs.items())):
        points: list[tuple[float, float]] = []
        invalid_values: list[str] = []
        for entry in entries:
            value = entry["affiliation_coordinates"] or ""
            if not value.strip():
                continue
            point = parse_stored_coordinates(value)
            if point is None:
                invalid_values.append(value)
            elif point not in points:
                points.append(point)

        result: dict[str, Any] = {
            "city": city,
            "country": country,
            "stored_points": [{"longitude": longitude, "latitude": latitude} for longitude, latitude in points],
            "invalid_coordinates": invalid_values,
            "nominatim_lon": None,
            "nominatim_lat": None,
            "point_results": [],
        }
        if invalid_values:
            result.update(status="INVALID_COORDINATES", reason="one or more stored coordinates are not finite WGS84 longitude,latitude points")
            counts["INVALID_COORDINATES"] += 1
            results.append(result)
            continue

        if not points:
            result.update(status="MISSING_COORDINATES", reason="no stored WGS84 longitude,latitude point")
            counts["MISSING_COORDINATES"] += 1
            results.append(result)
            continue

        hits = nominatim_city_search(city, country, cache, cache_path)
        if not hits:
            result.update(status="LOOKUP_FAILED", reason="Nominatim returned no city/country result")
            counts["LOOKUP_FAILED"] += 1
            results.append(result)
            continue

        try:
            nom_lon, nom_lat = float(hits[0]["lon"]), float(hits[0]["lat"])
        except (KeyError, TypeError, ValueError):
            result.update(status="LOOKUP_FAILED", reason="Nominatim returned invalid coordinates")
            counts["LOOKUP_FAILED"] += 1
            results.append(result)
            continue
        if not math.isfinite(nom_lon) or not math.isfinite(nom_lat) or not -180 <= nom_lon <= 180 or not -90 <= nom_lat <= 90:
            result.update(status="LOOKUP_FAILED", reason="Nominatim returned invalid coordinates")
            counts["LOOKUP_FAILED"] += 1
            results.append(result)
            continue

        result["nominatim_lon"] = nom_lon
        result["nominatim_lat"] = nom_lat
        point_statuses: list[str] = []
        for stored_lon, stored_lat in points:
            status = classify(stored_lon, stored_lat, nom_lon, nom_lat)
            point_statuses.append(status)
            result["point_results"].append({
                "longitude": stored_lon,
                "latitude": stored_lat,
                "status": status,
                "distance_km": round(haversine_km(stored_lon, stored_lat, nom_lon, nom_lat), 2),
                "degree_delta": round(degree_delta(stored_lon, stored_lat, nom_lon, nom_lat), 4),
            })

        if all(status == "MATCH" for status in point_statuses):
            status = "MATCH"
            reason = "all stored points match the Nominatim city/country result"
        elif "INVERTED" in point_statuses:
            status = "INVERTED"
            reason = "at least one stored point is latitude,longitude rather than longitude,latitude"
        else:
            status = "DISCREPANCY"
            reason = "at least one stored point does not match the Nominatim city/country result"
        result.update(status=status, reason=reason)
        counts[status] += 1
        results.append(result)

        if (i + 1) % 50 == 0:
            print(f"  checked {i + 1}/{len(pairs)}", file=sys.stderr)

    report = {"summary": {"total": len(pairs), "verified": counts["MATCH"], **counts}, "results": results}
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report["summary"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check affiliation_coordinates against Nominatim.")
    parser.add_argument("--db", default="awards.sqlite3", help="path to awards.sqlite3")
    parser.add_argument("--output", default="affiliation_coordinates_check.json", help="output JSON path")
    parser.add_argument("--cache", default=".nominatim-cache.json", help="cache file path")
    args = parser.parse_args(argv)

    cache_path = Path(args.cache)
    output_path = Path(args.output)

    print(f"checking affiliations in {args.db} ...", file=sys.stderr)
    summary = check_all(args.db, cache_path, output_path)
    print("summary " + " ".join(f"{key}={value}" for key, value in summary.items()))
    return 0 if summary["verified"] == summary["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
