#!/usr/bin/env python3
"""Reverse lookup longitude,latitude with OpenStreetMap Nominatim and print JSON."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "PrizeAtlas-reverse-lookup/1.0 (https://prizeatlas.org/)"


def parse_coordinates(value: str) -> tuple[float, float]:
    parts = value.split(",")
    if len(parts) != 2:
        raise ValueError("coordinates must be longitude,latitude")
    longitude, latitude = (float(part.strip()) for part in parts)
    if not math.isfinite(longitude) or not math.isfinite(latitude) or not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        raise ValueError("coordinates are outside WGS84 bounds")
    return longitude, latitude


def lookup(longitude: float, latitude: float, cache_path: Path) -> dict[str, Any]:
    key = f"{longitude},{latitude}"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    if key in cache:
        return cache[key]

    params = urllib.parse.urlencode({"lon": longitude, "lat": latitude, "format": "jsonv2", "addressdetails": 1})
    request = urllib.request.Request(f"{URL}?{params}", headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        result = json.load(response)
    if not isinstance(result, dict) or result.get("error"):
        raise ValueError(result.get("error", "Nominatim returned a non-object JSON response"))

    cache[key] = result
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n")
    time.sleep(1)
    return result


def clean(result: dict[str, Any]) -> dict[str, Any]:
    address = result.get("address")
    if not isinstance(address, dict):
        raise ValueError("Nominatim result has no address")
    city = next((address.get(key) for key in ("city", "town", "village", "municipality") if address.get(key)), None)
    state = next((address.get(key) for key in ("state", "region", "province") if address.get(key)), None)
    return {
        "city": city,
        "state": state,
        "country": address.get("country"),
        "country_code": address.get("country_code"),
        "display_name": result.get("display_name"),
        "osm_type": result.get("osm_type"),
        "osm_id": result.get("osm_id"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coordinates", required=True, help="longitude,latitude")
    parser.add_argument("--cache", default=".nominatim-reverse-cache.json")
    args = parser.parse_args(argv)

    try:
        longitude, latitude = parse_coordinates(args.coordinates)
        output = clean(lookup(longitude, latitude, Path(args.cache)))
    except (OSError, ValueError, TypeError, json.JSONDecodeError, urllib.error.URLError) as error:
        print(f"lookup failed: {error}", file=sys.stderr)
        return 1

    json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
