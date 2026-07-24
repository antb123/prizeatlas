#!/usr/bin/env python3
"""Enrich fields.csv with Wikidata-born/-died data for Fields Medalists.

Looks up each laureate by name via Wikidata search, then batches a single
wbgetentities call for all person + place + country entities. Fills:
  source_laureate_id, laureate_type, birth_date, birth_city, birth_country,
  birth_coordinates, death_date, death_city, death_country.

Leaves intentionally empty (Fields Medal has no sub-category, no citation,
equal individual share): category, motivation, prize_share, field_language.
"""
import csv
import json
import sys
import time
import urllib.parse
import urllib.request

WIKI = "https://www.wikidata.org/w/api.php"
UA = {"User-Agent": "fields-enrich/1.0 (nobel datasets cleanup)"}


DELAY = 3.0  # polite pause before every request


def api(params: dict) -> dict:
    time.sleep(DELAY)
    url = WIKI + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    for attempt in range(8):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < 7:
                time.sleep(min(2 ** attempt * 3 + 2, 60))
                continue
            raise


def search_qid(name: str) -> dict | None:
    data = api({
        "action": "wbsearchentities",
        "search": name,
        "language": "en",
        "format": "json",
        "limit": 1,
    })
    if not data.get("search"):
        return None
    hit = data["search"][0]
    return {
        "qid": hit["id"],
        "label": hit.get("label", ""),
        "description": hit.get("description", ""),
    }


def batch_entities(ids: list[str]) -> dict:
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        data = api({
            "action": "wbgetentities",
            "ids": "|".join(chunk),
            "props": "labels|claims",
            "languages": "en",
            "format": "json",
        })
        out.update(data.get("entities", {}))
        time.sleep(1.0)
    return out


def claim_value(ent: dict, prop: str) -> str | None:
    claims = ent.get("claims", {})
    if prop not in claims:
        return None
    snak = claims[prop][0]["mainsnak"]
    if "datavalue" not in snak:
        return None
    return snak["datavalue"]["value"]


def place_label_coords(ent: dict, prop: str, ents: dict) -> tuple[str, str, str]:
    """Return (city_label, country_label, coordinates) for a place claim."""
    qid = claim_value(ent, prop)
    if not qid:
        return "", "", ""
    place = ents.get(qid, {})
    city = place.get("labels", {}).get("en", {}).get("value", "")
    coords = ""
    if "P625" in place.get("claims", {}):
        v = claim_value(place, "P625")
        if isinstance(v, dict) and "latitude" in v:
            coords = f"{v['latitude']:.4f},{v['longitude']:.4f}"
    country = ""
    cq = claim_value(place, "P17")
    if cq and cq in ents:
        country = ents[cq].get("labels", {}).get("en", {}).get("value", "")
    return city, country, coords


def main() -> int:
    with open("fields.csv", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        rows = list(reader)

    # Pass 1: name -> Q-id (resumable: cache hits to a file)
    cache_path = "enrich_cache.json"
    qids: dict[str, str] = {}
    meta: dict[str, dict] = {}
    if __import__("os").path.exists(cache_path):
        with open(cache_path) as cf:
            qids = json.load(cf)
    for row in rows:
        name = row["full_name"]
        if name in qids and qids[name]:
            print(f"cached: {name} -> {qids[name]}", file=sys.stderr)
            continue
        hit = search_qid(name)
        if not hit:
            print(f"NO MATCH: {name}", file=sys.stderr)
            continue
        qids[name] = hit["qid"]
        meta[name] = hit
        with open(cache_path, "w") as cf:
            json.dump(qids, cf)

    # Collect all entity ids needed: persons + birth/death places + countries
    need: set[str] = set(qids.values())
    ents = batch_entities(list(need))
    for qid, ent in ents.items():
        for p in ("P19", "P20"):
            pq = claim_value(ent, p)
            if pq:
                need.add(pq)
        cq = claim_value(ent, "P17")
        if cq:
            need.add(cq)
    ents = batch_entities(list(need))

    # Apply
    filled = {k: 0 for k in (
        "source_laureate_id", "laureate_type", "birth_date", "birth_city",
        "birth_country", "birth_coordinates", "death_date", "death_city",
        "death_country",
    )}
    for row in rows:
        name = row["full_name"]
        if name not in qids:
            continue
        ent = ents[qids[name]]
        row["source_laureate_id"] = qids[name]
        filled["source_laureate_id"] += 1
        row["laureate_type"] = "Individual"
        filled["laureate_type"] += 1

        bdate = claim_value(ent, "P569")
        if isinstance(bdate, dict) and "time" in bdate:
            t = bdate["time"].lstrip("+").split("T")[0]
            if t.endswith("-00-00"):
                t = t[:4]
            elif t.endswith("-00"):
                t = t[:7]
            row["birth_date"] = t
            filled["birth_date"] += 1

        city, country, coords = place_label_coords(ent, "P19", ents)
        if city:
            row["birth_city"] = city
            filled["birth_city"] += 1
        if country:
            row["birth_country"] = country
            filled["birth_country"] += 1
        if coords:
            row["birth_coordinates"] = coords
            filled["birth_coordinates"] += 1

        ddate = claim_value(ent, "P570")
        if isinstance(ddate, dict) and "time" in ddate:
            t = ddate["time"].lstrip("+").split("T")[0]
            if t.endswith("-00-00"):
                t = t[:4]
            elif t.endswith("-00"):
                t = t[:7]
            row["death_date"] = t
            filled["death_date"] += 1
            dcity, dcountry, _ = place_label_coords(ent, "P20", ents)
            if dcity:
                row["death_city"] = dcity
                filled["death_city"] += 1
            if dcountry:
                row["death_country"] = dcountry
                filled["death_country"] += 1

    with open("fields.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)

    print("Enrichment summary (fields filled):")
    for k, v in filled.items():
        print(f"  {k:22} {v}")
    print("\nName -> Wikidata match (review for confidence):")
    for row in rows:
        name = row["full_name"]
        if name in meta:
            m = meta[name]
            print(f"  {name:35} -> {m['label']} [{m['description']}] {m['qid']}")
        else:
            print(f"  {name:35} -> ** NO MATCH **")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
