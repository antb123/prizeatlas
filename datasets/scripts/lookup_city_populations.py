#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["requests"]
# ///
# SPDX-License-Identifier: GPL-2.0-or-later
"""Look up GeoNames populations for a CSV of city and ISO country-code pairs."""

from __future__ import annotations

import argparse
import csv
import math
import os
import time
import unicodedata
from pathlib import Path

import requests

API_URL = "https://secure.geonames.org/searchJSON"


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    return "".join(character for character in value if not unicodedata.combining(character)).casefold().strip()


def distance_km(latitude: float, longitude: float, reference_latitude: str, reference_longitude: str) -> float:
    if not reference_latitude or not reference_longitude:
        return 0.0
    lat1, lon1, lat2, lon2 = map(math.radians, (latitude, longitude, float(reference_latitude), float(reference_longitude)))
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def lookup_city(city: str, country_code: str, state: str, reference_latitude: str, reference_longitude: str, username: str) -> dict[str, str | int | float]:
    response = requests.get(
        API_URL,
        params={
            "q": city,
            "country": country_code.upper(),
            "featureClass": "P",
            "isNameRequired": "true",
            "maxRows": 10,
            "style": "FULL",
            "username": username,
        },
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    if "status" in data:
        raise RuntimeError(data["status"].get("message", "GeoNames error"))

    candidates = data.get("geonames", [])
    if not candidates:
        return {"match_status": "not_found"}

    requested_name = normalize(city)
    requested_state = normalize(state)

    def score(place: dict) -> tuple[bool, bool, float, int]:
        names = {normalize(place.get("name", "")), normalize(place.get("toponymName", ""))}
        return (
            not requested_state or requested_state == normalize(place.get("adminName1", "")),
            requested_name in names,
            -distance_km(float(place["lat"]), float(place["lng"]), reference_latitude, reference_longitude),
            int(place.get("population") or 0),
        )

    candidates.sort(key=score, reverse=True)
    best = candidates[0]
    state_matches = not requested_state or requested_state == normalize(best.get("adminName1", ""))
    return {
        "population": best.get("population") or "",
        "matched_city": best.get("name", ""),
        "matched_state": best.get("adminName1", ""),
        "matched_country": best.get("countryName", ""),
        "latitude": best.get("lat", ""),
        "longitude": best.get("lng", ""),
        "geoname_id": best.get("geonameId", ""),
        "distance_to_affiliations_km": round(distance_km(float(best["lat"]), float(best["lng"]), reference_latitude, reference_longitude), 1),
        "match_status": "matched" if state_matches else "review_state",
        "candidate_count": len(candidates),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--username", default=os.environ.get("GEONAMES_USERNAME", ""))
    parser.add_argument("--delay", type=float, default=0.15)
    args = parser.parse_args()
    if not args.username:
        parser.error("provide --username or set GEONAMES_USERNAME")

    with args.input.open(newline="", encoding="utf-8-sig") as source:
        rows = list(csv.DictReader(source))

    output_rows = []
    for number, row in enumerate(rows, start=1):
        city = row["city"].strip()
        country_code = row["country_code"].strip()
        try:
            result = lookup_city(
                city,
                country_code,
                row.get("state", "").strip(),
                row.get("affiliation_latitude", "").strip(),
                row.get("affiliation_longitude", "").strip(),
                args.username,
            )
        except (requests.RequestException, RuntimeError, ValueError) as error:
            result = {"match_status": "error", "error": str(error)}
        output_rows.append({**row, **result})
        print(f"{number}/{len(rows)}: {city}, {country_code} -> {result.get('population', '')}")
        time.sleep(args.delay)

    fieldnames = list(dict.fromkeys(key for row in output_rows for key in row))
    with args.output.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
