#!/usr/bin/env python3
"""Enrich breakthrough.csv via Wikidata (scripted, cheap).

Fills, ONLY into EMPTY cells: source_laureate_id, birth_date, birth_city,
birth_country, sex, death_date, death_city, death_country.

Safety:
- Empty-cell-only: never overwrites existing values.
- Wrong-match guard: if the CSV already has a birth_year and the Wikidata
  entity's birth year disagrees, the whole record is SKIPPED (logged) so we
  never inject a wrong person's data. Common names are a real risk here.
Resumable via breakthrough_cache.json. Mirrors enrich_crafoord.py.
"""
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from os import path

WIKI = "https://www.wikidata.org/w/api.php"
UA = {"User-Agent": "breakthrough-enrich/1.0 (nobel datasets cleanup)"}
DELAY = 2.5
SEX = {"Q6581097": "Male", "Q6581072": "Female"}

TARGET_FIELDS = (
    "source_laureate_id", "birth_date", "birth_city", "birth_country",
    "sex", "death_date", "death_city", "death_country",
)


def api(params: dict) -> dict:
    time.sleep(DELAY)
    url = WIKI + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    for attempt in range(8):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except (urllib.error.HTTPError, TimeoutError, urllib.error.URLError):
            if attempt < 7:
                time.sleep(min(2 ** attempt * 3 + 2, 60))
                continue
            raise


def search_qid(name: str) -> dict | None:
    data = api({
        "action": "wbsearchentities", "search": name,
        "language": "en", "format": "json", "limit": 1,
    })
    if not data.get("search"):
        return None
    hit = data["search"][0]
    return {"qid": hit["id"], "label": hit.get("label", ""),
            "description": hit.get("description", "")}


def batch_entities(ids: list[str]) -> dict:
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        data = api({
            "action": "wbgetentities", "ids": "|".join(chunk),
            "props": "labels|claims", "languages": "en", "format": "json",
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
    v = snak["datavalue"]["value"]
    if isinstance(v, dict) and "id" in v:
        return v["id"]
    return v


def place_label(ent: dict, prop: str, ents: dict) -> str:
    qid = claim_value(ent, prop)
    if not qid or qid not in ents:
        return ""
    return ents[qid].get("labels", {}).get("en", {}).get("value", "")


def iso_date(v: dict) -> str:
    t = v["time"].lstrip("+").split("T")[0]
    if t.endswith("-00-00"):
        return t[:4]
    if t.endswith("-00"):
        return t[:7]
    return t


def birth_year_of(ent: dict) -> str | None:
    v = claim_value(ent, "P569")
    if isinstance(v, dict) and "time" in v:
        return v["time"].lstrip("+")[:4]
    return None


def main() -> int:
    with open("breakthrough.csv", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        rows = list(reader)

    cache_path = "breakthrough_cache.json"
    qids: dict[str, str] = {}
    meta: dict[str, dict] = {}
    if path.exists(cache_path):
        with open(cache_path) as cf:
            qids = json.load(cf)

    targets = [r for r in rows if not r["source_laureate_id"].strip()]
    target_ids = {r["award_record_id"] for r in targets}
    print(f"targets to enrich: {len(targets)}", file=sys.stderr)

    for row in targets:
        name = row["full_name"]
        if name in qids and qids[name]:
            continue
        hit = search_qid(name)
        if not hit:
            print(f"NO MATCH: {name}", file=sys.stderr)
            continue
        qids[name] = hit["qid"]
        meta[name] = hit
        with open(cache_path, "w") as cf:
            json.dump(qids, cf)

    need: set[str] = {qids[r["full_name"]] for r in targets if r["full_name"] in qids}
    ents = batch_entities(list(need))
    places: set[str] = set()
    for ent in ents.values():
        for p in ("P19", "P20"):
            pq = claim_value(ent, p)
            if pq:
                places.add(pq)
    need |= places
    ents = batch_entities(list(need))
    countries: set[str] = set()
    for q in places:
        cq = claim_value(ents[q], "P17") if q in ents else None
        if cq:
            countries.add(cq)
    need |= countries
    ents = batch_entities(list(need))

    filled = {k: 0 for k in TARGET_FIELDS}
    skipped_year = 0
    for row in rows:
        if row["award_record_id"] not in target_ids:
            continue
        name = row["full_name"]
        if name not in qids:
            continue
        ent = ents[qids[name]]
        # Wrong-match guard: if CSV birth_year conflicts with Wikidata, skip.
        cy = row["birth_year"]
        wy = birth_year_of(ent)
        if cy and wy and wy != cy:
            print(f"YEAR MISMATCH skip: {name} csv={cy} wd={wy} {qids[name]}",
                  file=sys.stderr)
            skipped_year += 1
            continue

        if not row["source_laureate_id"].strip():
            row["source_laureate_id"] = qids[name]
            filled["source_laureate_id"] += 1

        bdate = claim_value(ent, "P569")
        if isinstance(bdate, dict) and "time" in bdate and not row["birth_date"].strip():
            v = iso_date(bdate)
            if not cy or v.startswith(cy):
                row["birth_date"] = v
                filled["birth_date"] += 1

        if not row["birth_city"].strip():
            bc = place_label(ent, "P19", ents)
            if bc:
                row["birth_city"] = bc
                filled["birth_city"] += 1
        if not row["birth_country"].strip():
            pq = claim_value(ent, "P19")
            bcountry = ""
            if pq and pq in ents:
                cq = claim_value(ents[pq], "P17")
                if cq and cq in ents:
                    bcountry = ents[cq].get("labels", {}).get("en", {}).get("value", "")
            if bcountry:
                row["birth_country"] = bcountry
                filled["birth_country"] += 1

        if not row["sex"].strip():
            sx = claim_value(ent, "P21")
            if sx:
                row["sex"] = SEX.get(sx, ents.get(sx, {}).get("labels", {}).get("en", {}).get("value", ""))
                if row["sex"]:
                    filled["sex"] += 1

        ddate = claim_value(ent, "P570")
        if isinstance(ddate, dict) and "time" in ddate and not row["death_date"].strip():
            row["death_date"] = iso_date(ddate)
            filled["death_date"] += 1
            if not row["death_city"].strip():
                dc = place_label(ent, "P20", ents)
                if dc:
                    row["death_city"] = dc
                    filled["death_city"] += 1
            if not row["death_country"].strip():
                dq = claim_value(ent, "P20")
                dcountry = ""
                if dq and dq in ents:
                    cq = claim_value(ents[dq], "P17")
                    if cq and cq in ents:
                        dcountry = ents[cq].get("labels", {}).get("en", {}).get("value", "")
                if dcountry:
                    row["death_country"] = dcountry
                    filled["death_country"] += 1

    with open("breakthrough.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)

    print("Applied (empty cells only):")
    for k, v in filled.items():
        print(f"  {k:22} {v}")
    print(f"Year-mismatch skips: {skipped_year}")
    print("\nMatch report (review):")
    for name, m in meta.items():
        print(f"  {name:30} -> {m['label']} [{m['description']}] {qids[name]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
