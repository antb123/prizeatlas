#!/usr/bin/env python3
"""Look up a city with OpenStreetMap Nominatim and print JSON."""

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

URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "PrizeAtlas-city-lookup/1.0 (https://prizeatlas.org/)"


def search(city: str, country: str, state: str | None, cache_path: Path) -> list[dict[str, Any]]:
    query = {"city": city, "country": country, **({"state": state} if state else {})}
    key = json.dumps(query, ensure_ascii=False, sort_keys=True)
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    if key in cache:
        return cache[key]

    params = urllib.parse.urlencode({**query, "format": "jsonv2", "limit": 5})
    request = urllib.request.Request(f"{URL}?{params}", headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        results = json.load(response)
    if not isinstance(results, list):
        raise ValueError("Nominatim returned a non-list JSON response")

    cache[key] = results
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n")
    time.sleep(1)
    return results


def clean(result: dict[str, Any]) -> dict[str, Any]:
    longitude = float(result["lon"])
    latitude = float(result["lat"])
    if not math.isfinite(longitude) or not math.isfinite(latitude) or not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        raise ValueError("Nominatim returned invalid coordinates")
    return {
        "display_name": result.get("display_name", ""),
        "osm_type": result.get("osm_type", ""),
        "osm_id": result.get("osm_id"),
        "longitude": longitude,
        "latitude": latitude,
        "dataset_coordinates": f"{longitude:.4f},{latitude:.4f}",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", required=True)
    parser.add_argument("--country", required=True)
    parser.add_argument("--state")
    parser.add_argument("--cache", default=".nominatim-cache.json")
    args = parser.parse_args(argv)

    city = args.city.strip()
    country = args.country.strip()
    state = args.state.strip() if args.state else None
    if not city or not country:
        parser.error("--city and --country must not be empty")

    try:
        results = [clean(result) for result in search(city, country, state, Path(args.cache))]
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, urllib.error.URLError) as error:
        print(f"lookup failed: {error}", file=sys.stderr)
        return 1
    if not results:
        print(f"lookup failed: no result for {city}, {state + ', ' if state else ''}{country}", file=sys.stderr)
        return 1

    output = {"city": city, "country": country, **({"state": state} if state else {}), "results": results}
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2, allow_nan=False)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
