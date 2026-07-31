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


def nominatim_search(query: str, cache: dict[str, Any], cache_path: Path, rate_limit: float = RATE_LIMIT) -> list[dict[str, Any]]:
    if query in cache:
        return cache[query]

    params = urllib.parse.urlencode({"q": query, "format": "jsonv2", "limit": 1})
    request = urllib.request.Request(
        f"{NOMINATIM_URL}?{params}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            results = json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        results = []

    cache[query] = results
    save_cache(cache_path, cache)
    time.sleep(rate_limit)
    return results


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
    parts = value.split(",")
    if len(parts) != 2:
        return None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None


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
        "SELECT award_record_id, affiliation_name, affiliation_city, affiliation_country, affiliation_coordinates "
        "FROM awards WHERE affiliation_coordinates IS NOT NULL AND affiliation_coordinates != ''"
    ).fetchall()
    con.close()
    return [dict(row) for row in rows]


def check_all(db_path: str, cache_path: Path, output_path: Path) -> dict[str, Any]:
    cache = load_cache(cache_path)
    rows = fetch_affiliations(db_path)

    seen_queries: dict[str, tuple[float, float] | None] = {}
    results: list[dict[str, Any]] = []
    counts = {"MATCH": 0, "DISCREPANCY": 0, "INVERTED": 0, "NOT_FOUND": 0}

    for i, row in enumerate(rows):
        stored = parse_stored_coordinates(row["affiliation_coordinates"])
        if stored is None:
            results.append({**row, "status": "PARSE_ERROR", "nominatim_lon": None, "nominatim_lat": None, "distance_km": None, "degree_delta": None})
            counts["NOT_FOUND"] += 1
            continue

        stored_lon, stored_lat = stored
        query = f"{row['affiliation_name']}, {row['affiliation_city']}, {row['affiliation_country']}"

        if query not in seen_queries:
            hits = nominatim_search(query, cache, cache_path)
            if hits:
                seen_queries[query] = (float(hits[0]["lon"]), float(hits[0]["lat"]))
            else:
                fallback = nominatim_city_search(row["affiliation_city"], row["affiliation_country"], cache, cache_path)
                if fallback:
                    seen_queries[query] = (float(fallback[0]["lon"]), float(fallback[0]["lat"]))
                else:
                    seen_queries[query] = None

        nom = seen_queries[query]
        if nom is None:
            results.append({**row, "status": "NOT_FOUND", "nominatim_lon": None, "nominatim_lat": None, "distance_km": None, "degree_delta": None})
            counts["NOT_FOUND"] += 1
            continue

        nom_lon, nom_lat = nom
        status = classify(stored_lon, stored_lat, nom_lon, nom_lat)
        dist = haversine_km(stored_lon, stored_lat, nom_lon, nom_lat)
        delta = degree_delta(stored_lon, stored_lat, nom_lon, nom_lat)

        results.append({
            **row,
            "status": status,
            "nominatim_lon": nom_lon,
            "nominatim_lat": nom_lat,
            "distance_km": round(dist, 2),
            "degree_delta": round(delta, 4),
        })
        counts[status] += 1

        if (i + 1) % 50 == 0:
            print(f"  checked {i + 1}/{len(rows)}", file=sys.stderr)

    report = {"summary": {"total": len(rows), **counts}, "results": results}
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
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
