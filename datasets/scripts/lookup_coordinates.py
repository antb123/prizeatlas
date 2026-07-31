#!/usr/bin/env python3
"""Look up one city or institution and print its Wikidata coordinates as GeoJSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

WD_API = "https://www.wikidata.org/w/api.php"
WP_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "PrizeAtlas-coordinate-lookup/1.0 (https://prizeatlas.org/)"
EARTH_GLOBES = {
    "http://www.wikidata.org/entity/Q2",
    "https://www.wikidata.org/entity/Q2",
}
QID = re.compile(r"Q[1-9][0-9]*", re.IGNORECASE)

Entity = dict[str, Any]
Coordinate = tuple[float, float]  # longitude, latitude


class LookupFailure(Exception):
    """A lookup that cannot produce one verified coordinate."""


def api(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    query = {**params, "format": "json"}
    request = urllib.request.Request(
        f"{endpoint}?{urllib.parse.urlencode(query)}",
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response)
    except urllib.error.HTTPError as error:
        raise LookupFailure(f"Wikimedia API returned HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise LookupFailure(f"Wikimedia API request failed: {error}") from error

    if error := data.get("error"):
        raise LookupFailure(f"Wikimedia API error {error.get('code', 'unknown')}: {error.get('info', 'no details')}")
    return data


def wikipedia_qid(title: str) -> str | None:
    data = api(WP_API, {
        "action": "query",
        "prop": "pageprops",
        "ppprop": "wikibase_item",
        "redirects": 1,
        "formatversion": 2,
        "titles": title,
    })
    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return None
    return pages[0].get("pageprops", {}).get("wikibase_item")


def search_qids(query: str) -> list[str]:
    data = api(WD_API, {
        "action": "wbsearchentities",
        "search": query,
        "language": "en",
        "uselang": "en",
        "type": "item",
        "limit": 5,
    })
    return [hit["id"] for hit in data.get("search", []) if QID.fullmatch(hit.get("id", ""))]


def get_entities(qids: list[str]) -> dict[str, Entity]:
    if not qids:
        return {}
    data = api(WD_API, {
        "action": "wbgetentities",
        "ids": "|".join(qids),
        "props": "labels|descriptions|claims",
        "languages": "en",
    })
    return {
        qid: entity
        for qid, entity in data.get("entities", {}).items()
        if isinstance(entity, dict) and "missing" not in entity
    }


def best_coordinates(entity: Entity) -> list[Coordinate]:
    ranked: list[tuple[int, Coordinate]] = []
    for statement in entity.get("claims", {}).get("P625", []):
        if statement.get("rank") == "deprecated":
            continue
        value = statement.get("mainsnak", {}).get("datavalue", {}).get("value")
        if not isinstance(value, dict) or value.get("globe") not in EARTH_GLOBES:
            continue
        longitude = value.get("longitude")
        latitude = value.get("latitude")
        if (
            isinstance(longitude, (int, float))
            and not isinstance(longitude, bool)
            and isinstance(latitude, (int, float))
            and not isinstance(latitude, bool)
            and -180 <= longitude <= 180
            and -90 <= latitude <= 90
        ):
            rank = 0 if statement.get("rank") == "preferred" else 1
            ranked.append((rank, (float(longitude), float(latitude))))

    if not ranked:
        return []
    best_rank = min(rank for rank, _ in ranked)
    return list(dict.fromkeys(coordinate for rank, coordinate in ranked if rank == best_rank))


def entity_text(entity: Entity, field: str) -> str:
    return entity.get(field, {}).get("en", {}).get("value", "")


def describe(qid: str, entity: Entity) -> str:
    label = entity_text(entity, "labels") or qid
    description = entity_text(entity, "descriptions")
    return f"{qid} {label}" + (f" ({description})" if description else "")


def one_coordinate(qid: str, entity: Entity) -> Coordinate:
    coordinates = best_coordinates(entity)
    if not coordinates:
        raise LookupFailure(f"{describe(qid, entity)} has no usable Earth P625 coordinate")
    if len(coordinates) > 1:
        values = "; ".join(f"{longitude},{latitude}" for longitude, latitude in coordinates)
        raise LookupFailure(f"{describe(qid, entity)} has multiple equally ranked P625 coordinates: {values}")
    return coordinates[0]


def resolve(query: str) -> tuple[str, Entity, Coordinate, str]:
    if QID.fullmatch(query):
        qid = query.upper()
        entities = get_entities([qid])
        if qid not in entities:
            raise LookupFailure(f"Wikidata item {qid} does not exist")
        return qid, entities[qid], one_coordinate(qid, entities[qid]), "qid"

    if qid := wikipedia_qid(query):
        entities = get_entities([qid])
        if qid not in entities:
            raise LookupFailure(f"Wikipedia resolved to missing Wikidata item {qid}")
        return qid, entities[qid], one_coordinate(qid, entities[qid]), "wikipedia-title"

    qids = search_qids(query)
    entities = get_entities(qids)
    matches = [(qid, entities[qid], best_coordinates(entities[qid])) for qid in qids if qid in entities]
    located = [(qid, entity, coordinates) for qid, entity, coordinates in matches if coordinates]
    if not located:
        checked = "; ".join(describe(qid, entity) for qid, entity, _ in matches)
        suffix = f"; checked: {checked}" if checked else ""
        raise LookupFailure(f"no Wikidata search result has an Earth P625 coordinate{suffix}")
    if len(located) > 1:
        candidates = "; ".join(describe(qid, entity) for qid, entity, _ in located)
        raise LookupFailure(f"ambiguous query {query!r}; rerun with one Wikidata QID: {candidates}")

    qid, entity, coordinates = located[0]
    if len(coordinates) > 1:
        return qid, entity, one_coordinate(qid, entity), "wikidata-search"
    return qid, entity, coordinates[0], "wikidata-search"


def rounded(value: float) -> float:
    value = round(value, 4)
    return 0.0 if value == 0 else value


def geojson_feature(query: str, qid: str, entity: Entity, coordinate: Coordinate, match_method: str) -> dict[str, Any]:
    longitude, latitude = (rounded(value) for value in coordinate)
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [longitude, latitude],
        },
        "properties": {
            "query": query,
            "wikidata_id": qid,
            "label": entity_text(entity, "labels"),
            "description": entity_text(entity, "descriptions"),
            "match_method": match_method,
            "dataset_coordinates": f"{longitude:.4f},{latitude:.4f}",
            "source": f"https://www.wikidata.org/wiki/{qid}",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Look up one city or institution in Wikidata and print a GeoJSON Point.")
    parser.add_argument("query", help="city, institution, or Wikidata QID")
    parser.add_argument("--country", required=True, help="current country name used to qualify and validate the lookup")
    args = parser.parse_args(argv)
    query = args.query.strip()
    country = args.country.strip()
    if not query:
        parser.error("query must not be empty")
    if not country:
        parser.error("country must not be empty")

    try:
        lookup_query = query if QID.fullmatch(query) else f"{query}, {country}"
        qid, entity, coordinate, match_method = resolve(lookup_query)
    except LookupFailure as error:
        print(f"lookup failed: {error}", file=sys.stderr)
        return 1

    json.dump(geojson_feature(lookup_query, qid, entity, coordinate, match_method), sys.stdout, ensure_ascii=False, indent=2, allow_nan=False)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
